// SPDX-License-Identifier: MIT
pragma solidity ^0.8.19;

interface IERC20 {
    function transfer(address to, uint256 amount) external returns (bool);
    function transferFrom(address from, address to, uint256 amount) external returns (bool);
    function balanceOf(address account) external view returns (uint256);
}

contract VulnerableGovernanceVault {
    IERC20 public token;
    address public governance;
    uint256 public votingDelay;
    mapping(address => uint256) public emergencyFunds;

    constructor(address _token) {
        token = IERC20(_token);
        governance = msg.sender;
        votingDelay = 2 days;
    }

    function setVotingDelay(uint256 _newDelay) external {
        votingDelay = _newDelay;
    }

    function emergencyMigrate(address from, address to, uint256 amount) external {
        token.transferFrom(from, to, amount);
    }

    function depositEmergencyFunds(uint256 amount) external {
        require(amount > 0, "Amount must be > 0");
        emergencyFunds[msg.sender] += amount;
        token.transferFrom(msg.sender, address(this), amount);
    }

    function withdrawGovernanceFees(address recipient, uint256 amount) external {
        token.transfer(recipient, amount);
    }
}