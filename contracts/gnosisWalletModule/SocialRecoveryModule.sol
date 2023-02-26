// SPDX-License-Identifier: LGPL-3.0-only
pragma solidity ^0.8.12;

import "@openzeppelin/contracts/utils/cryptography/ECDSA.sol";
import "@safe-global/safe-contracts/contracts/common/Enum.sol";
import "./Module.sol";

/// @title Social Recovery Module - Allows to replace an owner without Safe confirmations if friends approve the replacement.
/// @author Stefan George - <stefan@gnosis.pm>
/// @author modified by SurfWallet Team

contract SocialRecoveryModule is Module {
    using ECDSA for bytes32;

    string public constant NAME = "Social Recovery Module";
    string public constant VERSION = "0.1.0_m";

    uint256 public threshold;
    address[] public friends;

    // isFriend mapping maps friend's address to friend status.
    mapping(address => bool) public isFriend;
    // isExecuted mapping maps data hash to execution status.
    mapping(bytes32 => bool) public isExecuted;
    // isConfirmed mapping maps data hash to friend's address to confirmation status.
    mapping(bytes32 => mapping(address => bool)) public isConfirmed;

    modifier onlyFriend() {
        require(isFriend[msg.sender], "Method can only be called by a friend");
        _;
    }

    /// @dev Setup function sets initial storage of contract.
    /// @param _friends List of friends' addresses.
    /// @param _threshold Required number of friends to confirm replacement.
    function setup(address[] memory _friends, uint256 _threshold) public {
        require(
            _threshold <= _friends.length,
            "Threshold cannot exceed friends count"
        );
        require(_threshold >= 2, "At least 2 friends required");
        setManager();
        // Set allowed friends.
        for (uint256 i = 0; i < _friends.length; i++) {
            address friend = _friends[i];
            require(friend != address(0), "Invalid friend address provided");
            require(!isFriend[friend], "Duplicate friend address provided");
            isFriend[friend] = true;
        }
        friends = _friends;
        threshold = _threshold;
    }

    /// @dev Allows a friend to confirm a Safe transaction.
    /// @param dataHash Safe transaction hash.
    function confirmTransaction(bytes32 dataHash) public onlyFriend {
        require(!isExecuted[dataHash], "Recovery already executed");
        isConfirmed[dataHash][msg.sender] = true;
    }

    /// @dev Returns if Safe transaction is a valid owner replacement transaction.
    /// @param prevOwner Owner that pointed to the owner to be replaced in the linked list
    /// @param oldOwner Owner address to be replaced.
    /// @param newOwner New owner address.
    /// @dev Returns if transaction can be executed.
    function recoverAccess(
        address prevOwner,
        address oldOwner,
        address newOwner
    ) public onlyFriend {
        bytes memory data = abi.encodeWithSignature(
            "swapOwner(address,address,address)",
            prevOwner,
            oldOwner,
            newOwner
        );
        bytes32 dataHash = getDataHash(data);
        require(!isExecuted[dataHash], "Recovery already executed");
        require(
            isConfirmedByRequiredFriends(dataHash),
            "Recovery has not enough confirmations"
        );
        isExecuted[dataHash] = true;
        require(
            manager.execTransactionFromModule(
                address(manager),
                0,
                data,
                Enum.Operation.Call
            ),
            "Could not execute recovery"
        );
    }

    /// @dev Returns if Safe transaction is a valid owner replacement transaction.
    /// @param prevOwner Owner that pointed to the owner to be replaced in the linked list
    /// @param oldOwner Owner address to be replaced.
    /// @param newOwner New owner address.
    /// @param signatures dataHash signed transactions by friends
    /// @dev Returns if transaction can be executed.
    function confirmAndRecoverAccess(
        address prevOwner,
        address oldOwner,
        address newOwner,
        bytes[] calldata signatures
    ) public onlyFriend {
        bytes memory data = abi.encodeWithSignature(
            "swapOwner(address,address,address)",
            prevOwner,
            oldOwner,
            newOwner
        );
        bytes32 dataHash = getDataHash(data);
        require(!isExecuted[dataHash], "Recovery already executed");
        require(
            signatures.length <= friends.length &&
                signatures.length >= threshold,
            "Wrong number of signatures"
        );
        for (uint256 i = 0; i < friends.length; i++) {
            address recoveredFriend = dataHash.recover(signatures[i]);
            require(
                isFriend[recoveredFriend] &&
                    !isConfirmed[dataHash][recoveredFriend],
                "Invalide Signature"
            );
            isConfirmed[dataHash][recoveredFriend] = true;
        }
        isExecuted[dataHash] = true;
        require(
            manager.execTransactionFromModule(
                address(manager),
                0,
                data,
                Enum.Operation.Call
            ),
            "Could not execute recovery"
        );
    }

    /// @dev Returns if Safe transaction is a valid owner replacement transaction.
    /// @param dataHash Data hash.
    /// @return Confirmation status.
    function isConfirmedByRequiredFriends(
        bytes32 dataHash
    ) public view returns (bool) {
        uint256 confirmationCount;
        for (uint256 i = 0; i < friends.length; i++) {
            if (isConfirmed[dataHash][friends[i]]) confirmationCount++;
            if (confirmationCount == threshold) return true;
        }
        return false;
    }

    /// @dev Returns hash of data encoding owner replacement.
    /// @param data Data payload.
    /// @return Data hash.
    function getDataHash(bytes memory data) public pure returns (bytes32) {
        return keccak256(data);
    }
}
