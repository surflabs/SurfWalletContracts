// SPDX-License-Identifier: LGPL-3.0-only
pragma solidity ^0.8.12;
import "./MasterCopy.sol";
import "./EIP4337Manager.sol";

/// @title Module - Base class for modules.
/// @author Stefan George - <stefan@gnosis.pm>
/// @author Richard Meissner - <richard@gnosis.pm>
contract Module is MasterCopy {

    EIP4337Manager public manager;

    modifier authorized() {
        require(msg.sender == address(manager), "Method can only be called from manager");
        _;
    }

    function setManager()
        internal
    {
        // manager can only be 0 at initalization of contract.
        // Check ensures that setup function can only be called once.
        require(address(manager) == address(0), "Manager has already been set");
        manager = EIP4337Manager(payable(msg.sender));
    }
}