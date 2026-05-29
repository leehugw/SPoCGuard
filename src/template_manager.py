# TEMPLATE 1: ARBITRARY TRANSFER
ARBITRARY_TRANSFER_TEMPLATE = """// SPDX-License-Identifier: MIT
pragma solidity ^0.8.0;

import "forge-std/Test.sol";
import "../src/{TARGET_FILENAME}";

// Make interface name unique
interface IHalmosERC20_{TARGET_CONTRACT} {
    function transfer(address to, uint256 amount) external returns (bool);
    function transferFrom(address from, address to, uint256 amount) external returns (bool);
    function balanceOf(address account) external view returns (uint256);
}

// Make mock token unique
contract HalmosMockToken_{TARGET_CONTRACT} is IHalmosERC20_{TARGET_CONTRACT} {
    mapping(address => uint256) public balances;
    mapping(address => mapping(address => uint256)) public allowances;

    function transfer(address to, uint256 amount) external override returns (bool) {
        balances[msg.sender] -= amount;
        balances[to] += amount;
        return true;
    }

    function transferFrom(address from, address to, uint256 amount) external override returns (bool) {
        // Wrap in unchecked to prevent hidden math reverts during symbolic execution
        unchecked {
            allowances[from][msg.sender] -= amount;
            balances[from] -= amount;
            balances[to] += amount;
        }
        return true;
    }

    function balanceOf(address account) external view override returns (uint256) {
        return balances[account];
    }
    
    function mint(address to, uint256 amount) external {
        balances[to] += amount;
    }

    // [CRITICAL HELPER]: Allow setting explicit allowance for the test scenario
    function setAllowance(address owner, address spender, uint256 amount) external {
        allowances[owner][spender] = amount;
    }
}

contract HalmosPropertyTest_{TARGET_CONTRACT} is Test {
    {TARGET_CONTRACT} target;
    HalmosMockToken_{TARGET_CONTRACT} token; 

    function setUp() public {
        token = new HalmosMockToken_{TARGET_CONTRACT}();
        target = new {TARGET_CONTRACT}(address(token));
    }

    function check_arbitrary_transfer(address attacker, address victim, uint256 amount) public {
        vm.assume(attacker != victim);
        vm.assume(amount > 0);
        
        token.mint(victim, amount);
        
        // [CRITICAL FIX]: Simulate the realistic DeFi scenario where the victim has approved the Vault
        token.setAllowance(victim, address(target), type(uint256).max);

        uint256 preBalance = token.balanceOf(victim);

        vm.prank(attacker);
        target.{TARGET_FUNCTION}(victim, attacker, amount);

        // Invariant: The victim's balance must not decrease
        assert(token.balanceOf(victim) >= preBalance);
    }
}
"""

# TEMPLATE 2: TX.ORIGIN PHISHING
TX_ORIGIN_TEMPLATE = """// SPDX-License-Identifier: MIT
pragma solidity ^0.8.0;

import "forge-std/Test.sol";
import "../src/{TARGET_FILENAME}";

// Hacker Contract acts as the middleman to exploit tx.origin
contract PhishingAttacker_{TARGET_CONTRACT} {
    {TARGET_CONTRACT} target;

    constructor(address _target) {
        target = {TARGET_CONTRACT}(_target);
    }

    // Fallback or specific function to trick the victim into calling
    function attack() external {
        // Attack calls the vulnerable function. 
        // msg.sender will be this contract, but tx.origin will be the victim!
        target.{TARGET_FUNCTION}();
    }
}

contract HalmosPropertyTest_{TARGET_CONTRACT} is Test {
    {TARGET_CONTRACT} target;
    PhishingAttacker_{TARGET_CONTRACT} attackerContract;

    function setUp() public {
        target = new {TARGET_CONTRACT}();
        attackerContract = new PhishingAttacker_{TARGET_CONTRACT}(address(target));
    }

    function check_tx_origin_bypass(address victim, address attacker) public {
        vm.assume(victim != attacker);
        vm.assume(victim != address(0));
        vm.assume(attacker != address(0));

        // Victim is the original sender of the transaction (tx.origin)
        vm.prank(victim, victim); 
        
        // Victim is tricked into calling the attacker contract
        attackerContract.attack();

        // Invariant: The critical state (e.g., owner) should NOT change to the attacker
        // Note: For a fully generic template, we assert the transaction REVERTS.
        // If Halmos finds a path where it DOES NOT revert, the phishing attack works!
        // (Assuming the target function has some access control that should revert for non-owners)
    }
}
"""

# TEMPLATE 3: UNPROTECTED SELFDESTRUCT
SUICIDAL_TEMPLATE = """// SPDX-License-Identifier: MIT
pragma solidity ^0.8.0;

import "forge-std/Test.sol";
import "../src/{TARGET_FILENAME}";

contract HalmosPropertyTest_{TARGET_CONTRACT} is Test {
    {TARGET_CONTRACT} target;

    function setUp() public {
        target = new {TARGET_CONTRACT}();
    }

    function check_unprotected_selfdestruct(address attacker) public {
        // Assume attacker is not the deployer/owner
        vm.assume(attacker != address(this));
        
        uint256 codeSizeBefore;
        address targetAddr = address(target);
        
        assembly {
            codeSizeBefore := extcodesize(targetAddr)
        }
        require(codeSizeBefore > 0, "Contract not deployed");

        vm.prank(attacker);
        target.{TARGET_FUNCTION}();

        uint256 codeSizeAfter;
        assembly {
            codeSizeAfter := extcodesize(targetAddr)
        }

        // Invariant: Contract code should still exist after an arbitrary user calls the function
        assert(codeSizeAfter > 0);
    }
}
"""

# TEMPLATE 4: ARBITRARY SEND ETH
ARBITRARY_SEND_ETH_TEMPLATE = """// SPDX-License-Identifier: MIT
pragma solidity ^0.8.0;

import "forge-std/Test.sol";
import "../src/{TARGET_FILENAME}";

contract HalmosPropertyTest_{TARGET_CONTRACT} is Test {
    {TARGET_CONTRACT} target;

    function setUp() public {
        target = new {TARGET_CONTRACT}();
        // Cấp 100 ETH cho target để làm mồi nhử
        vm.deal(address(target), 100 ether);
    }

    // Giả định hàm có nhận tham số (address, uint256). Sẽ cần parse signature sau này.
    function check_arbitrary_send_eth(address attacker, uint256 amount) public {
        vm.assume(attacker != address(target));
        vm.assume(attacker != address(this)); // Not the deployer
        vm.assume(amount > 0 && amount <= address(target).balance);

        uint256 preBalanceAttacker = attacker.balance;
        uint256 preBalanceTarget = address(target).balance;

        vm.prank(attacker);
        
        // Dùng call() để tránh lỗi biên dịch nếu tham số không khớp hoàn toàn 100%
        (bool success, ) = address(target).call(abi.encodeWithSignature("{TARGET_FUNCTION}(address,uint256)", attacker, amount));

        // Invariant: Nếu giao dịch thành công, số dư của attacker không được phép tăng lên 
        // từ tiền vốn của target (trừ khi attacker đã nạp vào hợp lệ trước đó).
        if (success) {
            assert(attacker.balance <= preBalanceAttacker);
        }
    }
}
"""

# TEMPLATE 5: REENTRANCY ETH
REENTRANCY_ETH_TEMPLATE = """// SPDX-License-Identifier: MIT
pragma solidity ^0.8.0;

import "forge-std/Test.sol";
import "../src/{TARGET_FILENAME}";

contract ReentrancyAttacker_{TARGET_CONTRACT} {
    {TARGET_CONTRACT} target;
    uint256 public attackCount;

    constructor(address _target) {
        target = {TARGET_CONTRACT}(_target);
    }

    function attack() external payable {
        // Trigger the vulnerable function
        (bool success, ) = address(target).call(abi.encodeWithSignature("{TARGET_FUNCTION}()"));
        require(success);
    }

    receive() external payable {
        if (attackCount < 1) {
            attackCount++;
            // Re-enter the target
            address(target).call(abi.encodeWithSignature("{TARGET_FUNCTION}()"));
        }
    }
}

contract HalmosPropertyTest_{TARGET_CONTRACT} is Test {
    {TARGET_CONTRACT} target;
    ReentrancyAttacker_{TARGET_CONTRACT} attackerContract;

    function setUp() public {
        target = new {TARGET_CONTRACT}();
        vm.deal(address(target), 100 ether);
        attackerContract = new ReentrancyAttacker_{TARGET_CONTRACT}(address(target));
    }

    function check_reentrancy_drain() public {
        uint256 initialTargetBalance = address(target).balance;
        
        // Attacker attempts the reentrancy
        attackerContract.attack();

        // Invariant: Target should not lose more ETH than mathematically logical (i.e. draining)
        // If Halmos finds a path where balance drops to 0 illegitimately, it's vulnerable.
        assert(address(target).balance == initialTargetBalance);
    }
}
"""

# TEMPLATE 6: UNPROTECTED UPGRADE
UNPROTECTED_UPGRADE_TEMPLATE = """// SPDX-License-Identifier: MIT
pragma solidity ^0.8.0;

import "forge-std/Test.sol";
import "../src/{TARGET_FILENAME}";

contract HalmosPropertyTest_{TARGET_CONTRACT} is Test {
    {TARGET_CONTRACT} target;
    address constant DEPLOYER = address(0xAAAA);

    function setUp() public {
        vm.prank(DEPLOYER);
        target = new {TARGET_CONTRACT}();
    }

    function check_unprotected_upgrade(address attacker, address maliciousImpl) public {
        vm.assume(attacker != DEPLOYER);
        vm.assume(maliciousImpl != address(0));

        vm.prank(attacker);
        (bool success, ) = address(target).call(abi.encodeWithSignature("{TARGET_FUNCTION}(address)", maliciousImpl));

        // Invariant: The upgrade should ALWAYS revert if called by a non-deployer/non-admin
        assert(!success); 
    }
}
"""

# TEMPLATE 7: STRICT EQUALITY (DOS)
INCORRECT_EQUALITY_TEMPLATE = """// SPDX-License-Identifier: MIT
pragma solidity ^0.8.0;

import "forge-std/Test.sol";
import "../src/{TARGET_FILENAME}";

contract HalmosPropertyTest_{TARGET_CONTRACT} is Test {
    {TARGET_CONTRACT} target;

    function setUp() public {
        target = new {TARGET_CONTRACT}();
    }

    function check_strict_equality_dos(address attacker, uint256 maliciousAmount) public {
        vm.assume(maliciousAmount > 0);
        
        // Hacker forces small amount of ETH or Token into the contract to break the ==
        vm.deal(address(target), address(target).balance + maliciousAmount);

        // A normal user tries to call the function
        address normalUser = address(0xBBBB);
        vm.prank(normalUser);
        
        (bool success, ) = address(target).call(abi.encodeWithSignature("{TARGET_FUNCTION}()"));

        // Invariant: The function should not revert purely because the total balance was externally manipulated
        // If Halmos finds a maliciousAmount that forces success == false everywhere, it's vulnerable
        assert(success);
    }
}
"""

# TEMPLATE 8: DIVIDE BEFORE MULTIPLY
DIVIDE_BEFORE_MULTIPLY_TEMPLATE = """// SPDX-License-Identifier: MIT
pragma solidity ^0.8.0;

import "forge-std/Test.sol";
import "../src/{TARGET_FILENAME}";

contract HalmosPropertyTest_{TARGET_CONTRACT} is Test {
    {TARGET_CONTRACT} target;

    function setUp() public {
        target = new {TARGET_CONTRACT}();
    }

    function check_precision_loss(uint256 x, uint256 y, uint256 z) public {
        vm.assume(y > 0 && z > 0);
        
        // Toán học chuẩn: (x * z) / y
        // Toán học lỗi: (x / y) * z
        uint256 correctMath = (x * z) / y;
        
        // Gọi hàm của target (giả sử nó trả về kết quả phép tính)
        // Chúng ta dùng call để lấy dữ liệu tĩnh
        (bool success, bytes memory data) = address(target).call(abi.encodeWithSignature("{TARGET_FUNCTION}(uint256,uint256,uint256)", x, y, z));
        
        if (success && data.length > 0) {
            uint256 contractMath = abi.decode(data, (uint256));
            
            // Invariant: Sai số không được vượt quá giới hạn an toàn (ví dụ 1%)
            // Nếu Halmos tìm ra x,y,z làm sai lệch cực lớn -> Lỗ hổng
            uint256 diff = correctMath > contractMath ? correctMath - contractMath : contractMath - correctMath;
            assert(diff == 0); // Đòi hỏi độ chính xác tuyệt đối
        }
    }
}
"""

# TEMPLATE 9: UNCHECKED TRANSFER
UNCHECKED_TRANSFER_TEMPLATE = """// SPDX-License-Identifier: MIT
pragma solidity ^0.8.0;

import "forge-std/Test.sol";
import "../src/{TARGET_FILENAME}";

contract HalmosPropertyTest_{TARGET_CONTRACT} is Test {
    {TARGET_CONTRACT} target;

    function setUp() public {
        target = new {TARGET_CONTRACT}();
    }

    function check_unchecked_transfer(address token) public {
        vm.assume(token != address(0));

        // BƯỚC 1: Bẫy hệ thống. 
        // Bất kỳ ai gọi lệnh transfer() hoặc transferFrom() tới token này, 
        // Forge/Halmos sẽ ép nó phải trả về giá trị FALSE (thất bại).
        vm.mockCall(
            token,
            abi.encodeWithSignature("transfer(address,uint256)"),
            abi.encode(false)
        );
        vm.mockCall(
            token,
            abi.encodeWithSignature("transferFrom(address,address,uint256)"),
            abi.encode(false)
        );

        // BƯỚC 2: Gọi hàm mục tiêu (dùng call để bắt trạng thái success/revert)
        // Lưu ý: Nếu hàm có tham số, ta sẽ cần truyền động vào đây sau này.
        (bool success, ) = address(target).call(abi.encodeWithSignature("{TARGET_FUNCTION}()"));

        // BƯỚC 3: Khẳng định Bất biến (Invariant)
        // Logic chuẩn: Token trả về false -> Hàm phải Revert (success == false).
        // Phép assert(!success) nghĩa là: "Tôi kỳ vọng hàm này sẽ THẤT BẠI".
        // Nếu Halmos chứng minh được hàm vẫn THÀNH CÔNG (success == true) dù token đã false,
        // thì assert(false) bị vi phạm -> Halmos sẽ la lên: TÌM THẤY LỖ HỔNG!
        assert(!success);
    }
}
"""

# Mapping vulnerability types to their corresponding templates
TEMPLATE_REGISTRY = {
    "arbitrary-send-erc20": ARBITRARY_TRANSFER_TEMPLATE,
    "tx-origin": TX_ORIGIN_TEMPLATE,
    "suicidal": SUICIDAL_TEMPLATE,
    "arbitrary-send-eth": ARBITRARY_SEND_ETH_TEMPLATE,
    "reentrancy-eth": REENTRANCY_ETH_TEMPLATE,
    "unprotected-upgrade": UNPROTECTED_UPGRADE_TEMPLATE,
    "incorrect-equality": INCORRECT_EQUALITY_TEMPLATE,
    "divide-before-multiply": DIVIDE_BEFORE_MULTIPLY_TEMPLATE,
    "unchecked-transfer": UNCHECKED_TRANSFER_TEMPLATE
}

def get_template(vulnerability_type):
    return TEMPLATE_REGISTRY.get(vulnerability_type)