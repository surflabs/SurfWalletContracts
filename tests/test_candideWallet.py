#!/usr/bin/python3

import pytest
from brownie import Contract, reverts, SurfWalletProxy
from web3.auto import w3
from eth_account.messages import defunct_hash_message
from eth_account import Account
from hexbytes import HexBytes
import eth_abi
from testUtils import *
from eip712.messages import EIP712Message, EIP712Type


def test_owner(surfWalletProxy, owner):
    """
    Check owner
    """
    assert surfWalletProxy.getOwners()[0] == owner


def test_transaction_from_proxy_directly(surfWalletProxy, owner,
                                         notOwner, bundler, tokenErc20, receiver, accounts):
    """
    Create a GnosisSafe transaction and call the proxy directly and check eth transfer
    """
    accounts[0].transfer(surfWalletProxy, "1 ether")  # Add ether to wallet
    beforeBalance = receiver.balance()
    nonce = 0

    # should revert if not the owner
    with reverts():
        ExecuteGnosisSafeExecTransaction(
            receiver.address,
            5,  # value to send
            "0x",
            0,
            0,
            0,
            0,
            '0x0000000000000000000000000000000000000000',
            '0x0000000000000000000000000000000000000000',
            nonce,
            notOwner,
            notOwner,
            surfWalletProxy)

    # should excute successfuly if from owner
    ExecuteGnosisSafeExecTransaction(
        receiver.address,
        5,  # value to send
        "0x",
        0,
        0,
        0,
        0,
        '0x0000000000000000000000000000000000000000',
            '0x0000000000000000000000000000000000000000',
            nonce,
            owner,
            owner,
            surfWalletProxy)

    # should revert if wrong nonce
    with reverts():
        ExecuteGnosisSafeExecTransaction(
            receiver.address,
            5,  # value to send
            "0x",
            0,
            0,
            0,
            0,
            '0x0000000000000000000000000000000000000000',
            '0x0000000000000000000000000000000000000000',
            nonce,
            notOwner,
            notOwner,
            surfWalletProxy)

    nonce = nonce + 1
    assert beforeBalance + 5 == receiver.balance()

    # should revert if value higher than balance
    with reverts():
        ExecuteGnosisSafeExecTransaction(
            receiver.address,
            surfWalletProxy.balance() + 1,
            "0x",
            0,
            0,
            0,
            0,
            '0x0000000000000000000000000000000000000000',
            '0x0000000000000000000000000000000000000000',
            nonce,
            notOwner,
            notOwner,
            surfWalletProxy)

    # mint erc20 for safe wallet to pay for the transaction gas with erc20
    amount = 100_000 * 10 ** 18
    tokenErc20._mint_for_testing(surfWalletProxy.address, amount)

    beforeBundlerErc20Balance = tokenErc20.balanceOf(bundler)
    beforeBalance = receiver.balance()

    # pay with transaction with erc20 by using a bundler/relayer
    ExecuteGnosisSafeExecTransaction(
        receiver.address,
        5,  # value to send
        "0x",
        0,
        215000,
        215000,
        100000,
        tokenErc20.address,
        bundler.address,
        nonce,
        owner,
        bundler,   # bundler/relayer that will sponsor the gas cost for erc20
        surfWalletProxy)

    # check if bundler was payed for relaying the transaction
    assert beforeBundlerErc20Balance < tokenErc20.balanceOf(bundler)
    assert beforeBalance + 5 == receiver.balance()


def test_transaction_through_entrypoint(surfWalletProxy, owner, bundler, receiver,
                                        entryPoint, accounts):
    """
    Create a GnosisSafe transaction through the EntryPoint
    """
    accounts[0].transfer(surfWalletProxy, "1 ether")  # Add ether to wallet
    beforeBalance = receiver.balance()
    nonce = 0

    entryPoint.depositTo(surfWalletProxy.address,
                         {'from': accounts[3], 'value': "1 ether"})

    # using execTransaction
    ExecuteEntryPointHandleOpsWithExecTransaction(
        receiver.address,
        5,  # value to send
        "0x",
        0,
        215000,
        215000,
        100000,
        "0x0000000000000000000000000000000000000000",
        "0x0000000000000000000000000000000000000000",
        nonce,
        owner,
        bundler,   # bundler/relayer that will sponsor the gas cost for erc20
        surfWalletProxy,
        "0x0000000000000000000000000000000000000000",
        bytes(0),
        entryPoint)
    assert beforeBalance + 5 == receiver.balance()


def test_transfer_from_entrypoint_with_init(surfWalletProxy,
                                            surfWalletSingleton, owner, bundler, receiver, notOwner, SurfWalletProxy,
                                            entryPoint, accounts, SocialRecoveryModule, friends):
    """
    Call entrypoint with initdata to create a surfWalletProxy then send eth
    """
    beforeBalance = receiver.balance()

    # initCode for deploying a new surfWalletProxy contract by the entrypoint
    walletProxyBytecode = SurfWalletProxy.bytecode
    walletProxyArgsEncoded = eth_abi.encode_abi(
        ['address'],
        [surfWalletSingleton.address]).hex()
    initCode = walletProxyBytecode + walletProxyArgsEncoded

    # send eth to the surfWalletProxy Contract address before deploying the surfWalletProxy contract
    proxyAdd = entryPoint.getSenderAddress(initCode, 0)
    accounts[0].transfer(proxyAdd, "1 ether")

    # create callData to be executed by the surfWalletProxy contract

    callData = surfWalletProxy.setup.encode_input(
        [owner.address],
        1,
        '0x0000000000000000000000000000000000000000',
        bytes(0),
        '0x0000000000000000000000000000000000000000',
        '0x0000000000000000000000000000000000000000',
        0,
        '0x0000000000000000000000000000000000000000')

    # deposit eth for the proxy contract in the entrypoint (no paymaster)
    entryPoint.depositTo(proxyAdd,
                         {'from': accounts[3], 'value': "1 ether"})

    nonce = 0

    # create entrypoint operation
    op = [
        proxyAdd,
        nonce,
        initCode,
        callData,
        215000,
        645000,
        21000,
        17530000000,
        17530000000,
        '0x0000000000000000000000000000000000000000',
        '0x',
        '0x'
    ]
    ExecuteEntryPointHandleOps(op, entryPoint, owner, bundler)

    # the new proxy deployed by the entrypoint
    deployedSurfWalletProxy = Contract.from_abi(
        "SurfWallet", proxyAdd, surfWalletSingleton.abi)

    ExecuteEntryPointHandleOpsWithExecTransaction(
        receiver.address,
        1000000000000000000,  # value to send
        "0x",
        0,
        215000,
        215000,
        100000,
        "0x0000000000000000000000000000000000000000",
        "0x0000000000000000000000000000000000000000",
        nonce,
        owner,
        bundler,   # bundler/relayer that will sponsor the gas cost for erc20
        deployedSurfWalletProxy,
        "0x0000000000000000000000000000000000000000",
        bytes(0),
        entryPoint)

    assert beforeBalance + 1000000000000000000 == receiver.balance()

    """
    Test Social Recovry
    """
    # setup social recovery
    deployedSurfWalletProxy.setupSocialRecovery(friends, 2, {'from': owner})

    assert deployedSurfWalletProxy.friends(0) == friends[0]
    assert deployedSurfWalletProxy.friends(1) == friends[1]

    newOwner = accounts[6]
    prevOwner = '0x0000000000000000000000000000000000000001'
    recoveryData = surfWalletProxy.swapOwner.encode_input(
        prevOwner,
        owner.address,
        newOwner.address)
    dataHash = deployedSurfWalletProxy.getDataHash(recoveryData,
                                                   {'from': friends[0]})

    friend0Signer = w3.eth.account.from_key(friends[0].private_key)
    sigFriend0 = friend0Signer.signHash(dataHash)

    friend1Signer = w3.eth.account.from_key(friends[1].private_key)
    sigFriend1 = friend1Signer.signHash(dataHash)

    notOwnerSigner = w3.eth.account.from_key(notOwner.private_key)
    sigNotOwner = notOwnerSigner.signHash(dataHash)

    # will revert if wrong signatures
    with reverts():
        deployedSurfWalletProxy.recoverAccess(prevOwner, owner.address,
                                              newOwner.address, [
                                                  sigNotOwner.signature.hex(), sigFriend1.signature.hex()],
                                              {'from': friends[0]})

    deployedSurfWalletProxy.recoverAccess(prevOwner, owner.address,
                                          newOwner.address, [
                                              sigFriend0.signature.hex(), sigFriend1.signature.hex()],
                                          {'from': friends[0]})

    # check old owner is not owner anymore
    assert deployedSurfWalletProxy.isOwner(owner, {'from': notOwner}) == False

    # check new owner is the current owner
    assert deployedSurfWalletProxy.isOwner(
        newOwner, {'from': notOwner}) == True


def test_transfer_from_entrypoint_with_deposit_paymaster(surfWalletProxy, tokenErc20,
                                                         owner, bundler, entryPoint, depositPaymaster, receiver, accounts):
    """
    Test sponsor transaction fees with erc20 with a deposit paymaster
    """
    accounts[0].transfer(surfWalletProxy, "1 ether")
    beforeBalance = receiver.balance()

    accounts[0].transfer(owner, "3 ether")
    depositPaymaster.addStake(100, {'from': owner, 'value': "1 ether"})
    depositPaymaster.deposit({'from': owner, 'value': "1 ether"})

    #assert "1 ether" == entryPoint.getDepositInfo(paymaster.address, {'from':owner})
    tokenErc20.approve(depositPaymaster.address, "1 ether", {'from': bundler})
    tokenErc20.transfer(surfWalletProxy.address, "1 ether", {'from': bundler})
    bundlerBalance = tokenErc20.balanceOf(bundler)
    depositPaymaster.addDepositFor(tokenErc20.address, surfWalletProxy.address, "1 ether",
                                   {'from': bundler})
    paymasterData = depositPaymaster.address[2:] + tokenErc20.address[2:]

    ExecuteEntryPointHandleOpsWithExecTransaction(
        receiver.address,
        5,  # value to send
        "0x",
        0,
        215000,
        215000,
        100000,
        tokenErc20.address,
        bundler.address,
        0,
        owner,
        bundler,
        surfWalletProxy,
        depositPaymaster.address,
        paymasterData,
        entryPoint)

    assert beforeBalance + 5 == receiver.balance()  # verifing eth is sent


def test_transfer_from_entrypoint_with_verification_paymaster(surfWalletProxy, tokenErc20,
                                                              owner, bundler, entryPoint, verifyingPaymaster, receiver, accounts):
    """
    Test sponsor transaction fees with erc20 with a verification paymaster
    """
    accounts[0].transfer(surfWalletProxy, "1 ether")
    beforeBalance = receiver.balance()

    accounts[0].transfer(bundler, "3 ether")
    verifyingPaymaster.addStake(100, {'from': bundler, 'value': "1 ether"})
    verifyingPaymaster.deposit({'from': bundler, 'value': "1 ether"})

    tokenErc20.approve(verifyingPaymaster.address,
                       "1 ether", {'from': bundler})
    tokenErc20.transfer(surfWalletProxy.address, "1 ether", {'from': bundler})
    bundlerBalance = tokenErc20.balanceOf(bundler)

    tx_hash = surfWalletProxy.getTransactionHash(
        receiver.address,
        5,  # value to send
        "0x",
        0,
        215000,
        215000,
        100000,
        tokenErc20.address,
        bundler.address,
        1)

    contract_transaction_hash = HexBytes(tx_hash)
    ownerSigner = Account.from_key(owner.private_key)
    signature = ownerSigner.signHash(contract_transaction_hash)

    callData = surfWalletProxy.execTransaction.encode_input(
        receiver.address,
        5,  # value to send
        "0x",
        0,
        215000,
        215000,
        100000,
        tokenErc20.address,
        bundler.address,
        signature.signature.hex())

    op = [
        surfWalletProxy.address,
        0,
        bytes(0),
        callData,
        2150000,
        645000,
        21000,
        17530000000,
        17530000000,
        verifyingPaymaster.address,
        '0x',
        '0x'
    ]
    datahash = verifyingPaymaster.getHash(op)
    bundlerSigner = w3.eth.account.from_key(bundler.private_key)
    sig = bundlerSigner.signHash(datahash)

    paymasterData = sig.signature

    op = [
        surfWalletProxy.address,
        0,
        bytes(0),
        callData,
        2150000,
        645000,
        21000,
        17530000000,
        17530000000,
        verifyingPaymaster.address,
        paymasterData.hex(),
        '0x'
    ]

    requestId = entryPoint.getRequestId(op)
    ownerSigner = w3.eth.account.from_key(owner.private_key)
    message_hash = defunct_hash_message(requestId)
    sig = ownerSigner.signHash(message_hash)
    op[11] = sig.signature
    entryPoint.handleOps([op], bundler, {'from': bundler})

    assert beforeBalance + 5 == receiver.balance()  # verifing eth is sent
    # verify bundler is payed
    assert tokenErc20.balanceOf(bundler) > bundlerBalance
