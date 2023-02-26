from brownie import Contract, SafeProxy4337, EIP4337Manager, TokenPriceOracle, DepositPaymaster, VerifyingPaymaster, SurfWallet, SurfWalletProxy, accounts, network
from brownie_tokens import ERC20


entryPoint_addr = "0x56D3a032C1ddD051BB4a8A75f3A8D9D7e802CD1d"
create2factory_address = "0xce0042b868300000d44a59004da54a005ffdcf9f"
gnosis_safe_singleton_addr = "0x3E5c63644E683549055b9Be8653de26E0B4CD36E"


def main():
    isPublish = False

    friends = []
    owner = accounts.load("111")
    bundler = accounts.load("222")
    friends.append(owner)
    friends.append(bundler)

    manager = EIP4337Manager.deploy(entryPoint_addr,
                                    {'from': owner}, publish_source=isPublish)

    safeProxy = SafeProxy4337.deploy(gnosis_safe_singleton_addr, manager.address,
                                     owner.address, friends, 2, {'from': owner}, publish_source=isPublish)

    depositPaymaster = DepositPaymaster.deploy(entryPoint_addr,
                                               {'from': owner}, publish_source=isPublish)

    tokenOracle = TokenPriceOracle.deploy(
        {'from': owner}, publish_source=isPublish)

    depositPaymaster.addToken(
        tokenOracle.address, tokenOracle.address, {'from': owner})

    VerifyingPaymaster.deploy(entryPoint_addr, bundler,
                              {'from': bundler}, publish_source=isPublish)

    SurfWalletSingleton = SurfWallet.deploy(entryPoint_addr,
                                            {'from': owner}, publish_source=isPublish)

    SurfWalletProxy.deploy(SurfWalletSingleton.address,
                           {'from': owner}, publish_source=isPublish)
