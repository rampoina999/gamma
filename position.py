import web3
def positionKey(ownerAddress, tickLower, tickUpper):
    val_types = ["address","int24","int24"]
    values = [ownerAddress,tickLower,tickUpper]
    return web3.Web3.solidityKeccak(val_types, values).hex()


gammas_pos = positionKey(ownerAddress=web3.Web3.toChecksumAddress("0xd7b990543ea8e9bd0b9ae2deb9c52c4d0e660431".lower()),
            tickLower=-276328,
            tickUpper=-276322,
            )

arrakis_pos = positionKey(ownerAddress="0x50379f632ca68D36E50cfBC8F78fe16bd1499d1e",
            tickLower=-276326,
            tickUpper=-276322,
            )

print( gammas_pos)  # result -> 0x03f0f38ca89a70f8b2c2ffe9ad6cc2e7ddaa35532a0183d677bc2460d5000bd1
print( arrakis_pos) # result -> 0xfde440200d6e116e87fbe0fc1ec51d36ec2add59fa2f8fef44436d04b5d92e99

# check at https://etherscan.io/address/0x5777d92f208679db4b9778590fa3cab3ac9e2168#readContract
