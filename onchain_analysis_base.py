from web3 import Web3
import logging

import math
import datetime as dt
from eth_abi import abi
from hexbytes import HexBytes

from bins import file_utilities


_x96 = 2**96
_x128 = math.pow(2, 128)


# GENERAL
class web3wrap():
    
    _abi_filename = "" # json file name without the extension
    _abi_path = ""  # like data/abi/gamma
    _abi = ""

    _address = ""
    _w3 = None
    _contract = None
    _block = 0

    _cache = dict() # cached vars like decimals, name...
    _progress_callback = None

   # SETUP
    def __init__(self, address:str, web3Provider:Web3=None, web3Provider_url:str="", abi_filename:str="", abi_path:str="",
                        block:int=0):
        # set init vars
        address = Web3.toChecksumAddress(address)
        self._address = address
        # set optionals
        self.setup_abi(abi_filename=abi_filename, abi_path=abi_path)
        # setup Web3 
        self.setup_w3(web3Provider=web3Provider, web3Provider_url=web3Provider_url)
        # setup contract to query
        self.setup_contract(address=address, abi=self._abi)

        # set block
        self._block = self._w3.eth.get_block("latest").number if block == 0 else block
    
    def setup_abi(self, abi_filename:str, abi_path:str):
        # set optionals
        if abi_filename != "":
            self._abi_filename = abi_filename
        if abi_path != "":
            self._abi_path = abi_path
        # load abi
        self._abi = file_utilities.load_json(filename=self._abi_filename, folder_path=self._abi_path)

    def setup_w3(self, web3Provider, web3Provider_url:str):
        # create Web3 helper
        if web3Provider == None and web3Provider_url != "":
            self._w3 =  Web3(Web3.HTTPProvider(web3Provider_url,request_kwargs={'timeout': 120}))  #request_kwargs={'timeout': 60}))
        elif web3Provider != None:
            self._w3 = web3Provider
        else:
            raise ValueError(" Either web3Provider or web3Provider_url var should be defined")

    def setup_contract(self, address:str, abi:str):
        # set contract
        self._contract = self._w3.eth.contract(address=address, abi=abi)

   # CUSTOM PROPERTIES
    @property
    def address(self)->str:
        return self._address
    # @address.setter
    # def address(self, value:str):
    #     self._address = value
    
    @property
    def w3(self)->Web3:
        return self._w3
    # @w3.setter
    # def w3(self, value:Web3):
    #     self._w3 = value

    @property
    def contract(self)->str:
        return self._contract
    # @contract.setter
    # def contract(self, value:str):
    #     self._contract = value

    @property
    def block(self)->int:
        """ """
        return self._block
    @block.setter
    def block(self, value:int):
        self._block = value
    # @x.deleter
    # def block(self):
    #     del self._block

   # HELPERS
    def average_blockTime(self, blocksaway=500)->dt.datetime.timestamp:
        """ Average time of block creation

         Args:
            blocksaway (int, optional): blocks used compute average. Defaults to 500.

         Returns:
            dt.datetime.timestamp: average time per block
        """        
        result = 0
        if blocksaway >0:
            block_curr = self._w3.eth.get_block('latest')
            block_past = self._w3.eth.get_block(block_curr.number-blocksaway)
            result = (block_curr.timestamp-block_past.timestamp)/blocksaway
        return result

    def blockNumberFromTimestamp(self, timestamp:dt.datetime.timestamp)->int:
        """ Will 
            At least 15 queries are needed to come close to a timestamp block number
            
         Args:
            timestamp (dt.datetime.timestamp): _description_

         Returns:
            int: blocknumber 
        """        
        
        if int(timestamp) == 0:
            raise ValueError("Timestamp cannot be zero!")

        queries_cost = 0

        block_curr = self._w3.eth.get_block('latest')
        first_step = math.ceil(block_curr.number*0.85)

        # make sure we have positive block result
        while (block_curr.number+first_step) <= 0:
            first_step -= 1
        # calc blocks to go up/down closer to goal
        block_past = self._w3.eth.get_block(block_curr.number-(first_step))
        blocks_x_timestamp = abs(block_curr.timestamp-block_past.timestamp)/first_step
        
        block_step = (block_curr.timestamp-timestamp)/ blocks_x_timestamp
        block_step_sign = -1

        _startime = dt.datetime.utcnow()

        while block_curr.timestamp != timestamp:
            
            queries_cost+=1

            # make sure we have positive block result
            while (block_curr.number+(block_step*block_step_sign)) <= 0:
                if queries_cost == 1:
                    # first time here, set lower block steps
                    block_step /= 2
                else:
                    # change sign and lower steps
                    block_step_sign *= -1
                    block_step /= 2

            # go to block
            block_curr = self._w3.eth.get_block(math.floor(block_curr.number + (block_step*block_step_sign)))

            blocks_x_timestamp = (abs(block_curr.timestamp-block_past.timestamp)/abs(block_curr.number-block_past.number)) if abs(block_curr.number-block_past.number) != 0 else 0
            if blocks_x_timestamp != 0:
                block_step = math.ceil(abs(block_curr.timestamp-timestamp)/blocks_x_timestamp)

            if block_curr.timestamp < timestamp:
                # block should be higher than current
                block_step_sign = 1
            elif block_curr.timestamp > timestamp:
                # block should be lower than current
                block_step_sign = -1
            else:
                # got it 
                logging.getLogger(__name__).debug(" Took {} queries to the chain to find block number {} of timestamp {}".format(queries_cost, block_curr.number, timestamp))
                return block_curr.number

            # set block past 
            block_past = block_curr

            # 15sec while loop safe exit (an eternity to find the block)
            if (dt.datetime.utcnow() - _startime).total_seconds() > (15):
                if (timestamp-block_curr.timestamp) < 0:
                    # modify block so it is not beyond timestamp
                    block_curr = self._w3.eth.get_block(block_curr.number-1)
                logging.getLogger(__name__).warning(" Could not find exact block number from timestamp -> took {} queries to the chain to find block number {} ({}) closest to timestamp {}  -> original-found difference {}".format(queries_cost, block_curr.number, block_curr.timestamp, timestamp, timestamp-block_curr.timestamp))
                break
        
        # return closest block found
        return block_curr.number

    def create_eventFilter_chunks(self, eventfilter:dict, max_blocks=1000)->list:
        """ create a list of event filters 
            to be able not to timeout servers

         Args:
            eventfilter (dict):  {'fromBlock': GAMMA_START_BLOCK,
                                    'toBlock': block,
                                    'address': [self._address],
                                    'topics': [self._topics[operation]],
                                    }

         Returns:
            list: of the same
         """       
        result = list()
        tmp_filter = {k:v for k,v in eventfilter.items()}
        toBlock = eventfilter["toBlock"]
        fromBlock = eventfilter["fromBlock"]
        blocksXfilter = math.ceil((toBlock-fromBlock)/max_blocks)

        current_fromBlock = tmp_filter["fromBlock"]
        current_toBlock = current_fromBlock+max_blocks
        for i in range(blocksXfilter):
            
            # mod filter blocks
            tmp_filter["toBlock"] = current_toBlock
            tmp_filter["fromBlock"] = current_fromBlock
            
            # append filter
            result.append({k:v for k,v in tmp_filter.items()})

            # exit if done...
            if current_toBlock == toBlock:
                break

            # increment chunk
            current_fromBlock = current_toBlock + 1
            current_toBlock = (current_fromBlock + max_blocks)
            if current_toBlock > toBlock:
                current_toBlock = toBlock
        
        # return result
        return result

    def get_chunked_events(self, eventfilter, max_blocks=5000):
        # get a list of filters with different block chunks
        for filter in self.create_eventFilter_chunks(eventfilter=eventfilter, max_blocks=max_blocks):
            entries = self._w3.eth.filter(filter).get_all_entries()
            
            # progress if no data found
            if self._progress_callback and len(entries) == 0:
                self._progress_callback(text="no matches from blocks {} to {}".format(filter["fromBlock"], filter["toBlock"]), 
                                        remaining=eventfilter["toBlock"]-filter["toBlock"], 
                                        total=eventfilter["toBlock"]-eventfilter["fromBlock"]) 

            # filter blockchain data
            for event in entries:
                yield event
            
class erc20(web3wrap):
    _abi_filename = "erc20"
    _abi_path = "data/abi"
    
   # PROPERTIES
    @property
    def decimals(self)->int:
        return self._contract.functions.decimals().call(block_identifier=self.block)
    
    def balanceOf(self, address:str)->float:
        return self._contract.functions.balanceOf(Web3.toChecksumAddress(address)).call(block_identifier=self.block)/(10**self.decimals)
    
    @property
    def totalSupply(self)->float:
        return self._contract.functions.totalSupply().call(block_identifier=self.block)/(10**self.decimals)
    
    @property
    def symbol(self)->str:
        return self._contract.functions.symbol().call(block_identifier=self.block)
    
    def allowance(self, owner:str, spender:str)->float:
        return self._contract.functions.allowance(Web3.toChecksumAddress(owner), Web3.toChecksumAddress(spender)).call(block_identifier=self.block)/(10**self.decimals)


# EXCHANGES
class univ3_pool(erc20):
    _abi_filename = "univ3_pool"
    _abi_path = "data/abi/uniswap/v3"

    _token0:erc20 = None
    _token1:erc20 = None

    @property
    def factory(self)->str:
        return self._contract.functions.factory().call(block_identifier=self.block)

    @property
    def fee(self)->int:
        """ The pool's fee in hundredths of a bip, i.e. 1e-6  

        """        
        return self._contract.functions.fee().call(block_identifier=self.block)

    @property
    def feeGrowthGlobal0X128(self)->int:
        """ The fee growth as a Q128.128 fees of token0 collected per unit of liquidity for the entire life of the pool
         Returns:
            int: as Q128.128 fees of token0
         """      
        return self._contract.functions.feeGrowthGlobal0X128().call(block_identifier=self.block)
    
    @property
    def feeGrowthGlobal1X128(self)->int:
        """ The fee growth as a Q128.128 fees of token1 collected per unit of liquidity for the entire life of the pool
         Returns:
            int: as Q128.128 fees of token1
         """        
        return self._contract.functions.feeGrowthGlobal1X128().call(block_identifier=self.block)

    @property
    def liquidity(self)->int:
        return self._contract.functions.liquidity().call(block_identifier=self.block)

    @property
    def maxLiquidityPerTick(self)->int:
        return self._contract.functions.maxLiquidityPerTick().call(block_identifier=self.block)
    
    def observations(self, input:int):
        return self._contract.functions.observations(input).call(block_identifier=self.block)
    
    def observe(self, secondsAgo:int):
        """observe _summary_

         Args:
            secondsAgo (int): _description_

         Returns:
            _type_: tickCumulatives   int56[] :  12731930095582
                    secondsPerLiquidityCumulativeX128s   uint160[] :  242821134689165142944235398318169
            
         """        
        return self._contract.functions.observe(secondsAgo).call(block_identifier=self.block)

    def positions(self, position_key:str)->dict:
        """ 

         Args:
            position_key (str): 0x....

         Returns:
            _type_: 
                    liquidity   uint128 :  99225286851746
                    feeGrowthInside0LastX128   uint256 :  0
                    feeGrowthInside1LastX128   uint256 :  0
                    tokensOwed0   uint128 :  0
                    tokensOwed1   uint128 :  0
         """
        result = self._contract.functions.positions(position_key).call(block_identifier=self.block)
        return {"liquidity":result[0],
                "feeGrowthInside0LastX128":result[1],
                "feeGrowthInside1LastX128":result[2],
                "tokensOwed0":result[3],
                "tokensOwed1":result[4],
                }

    @property  
    def protocolFees(self):
        """ The amounts of token0 and token1 that are owed to the protocol

         Returns:
            _type_: token0   uint128 :  0
                    token1   uint128 :  0
         """        
        return self._contract.functions.protocolFees().call(block_identifier=self.block)

    @property
    def slot0(self)->dict:
        """ The 0th storage slot in the pool stores many values, and is exposed as a single method to save gas when accessed externally.

         Returns:
            _type_: sqrtPriceX96   uint160 :  28854610805518743926885543006518067
                    tick   int24 :  256121
                    observationIndex   uint16 :  198
                    observationCardinality   uint16 :  300
                    observationCardinalityNext   uint16 :  300
                    feeProtocol   uint8 :  0
                    unlocked   bool :  true
         """
        tmp = self._contract.functions.slot0().call(block_identifier=self.block)
        return {
                "sqrtPriceX96": tmp[0],
                "tick": tmp[1],
                "observationIndex": tmp[2],
                "observationCardinality": tmp[3],
                "observationCardinalityNext": tmp[4],
                "feeProtocol": tmp[5],
                "unlocked": tmp[6],
        }

    def snapshotCumulativeInside(self, tickLower:int, tickUpper:int):
        return self._contract.functions.snapshotCumulativeInside(tickLower,tickUpper).call(block_identifier=self.block)

    def tickBitmap(self, input:int)->int:
        return self._contract.functions.tickBitmap(input).call(block_identifier=self.block)

    @property
    def tickSpacing(self)->int:
        return self._contract.functions.tickSpacing().call(block_identifier=self.block)

    def ticks(self, tick:int)->dict:
        """  

         Args:
            tick (int): 

         Returns:
            _type_:     liquidityGross   uint128 :  0
                        liquidityNet   int128 :  0
                        feeGrowthOutside0X128   uint256 :  0
                        feeGrowthOutside1X128   uint256 :  0
                        tickCumulativeOutside   int56 :  0
                        secondsPerLiquidityOutsideX128   uint160 :  0
                        secondsOutside   uint32 :  0
                        initialized   bool :  false
         """
        result = self._contract.functions.ticks(tick).call(block_identifier=self.block)
        return {"liquidityGross":result[0],
                "liquidityNet":result[1],
                "feeGrowthOutside0X128":result[2],
                "feeGrowthOutside1X128":result[3],
                "tickCumulativeOutside":result[4],
                "secondsPerLiquidityOutsideX128":result[5],
                "secondsOutside":result[6],
                "initialized":result[7],
            }

    @property
    def token0(self)->erc20:
        """ The first of the two tokens of the pool, sorted by address

         Returns:
            erc20: 
         """        
        if self._token0 == None:
            self._token0 = erc20(address=self._contract.functions.token0().call(block_identifier=self.block),
                                 web3Provider=self._w3)
        return self._token0
    
    @property
    def token1(self)->erc20:
        """The second of the two tokens of the pool, sorted by address_

         Returns:
            erc20: 
         """        
        if self._token1 == None:
            self._token1 = erc20(address=self._contract.functions.token1().call(block_identifier=self.block),
                                 web3Provider=self._w3)
        return self._token1
    
   #WRITE FUNCTION WITHOUT STATE CHANGE
    def collect(self, recipient, tickLower, tickUpper, amount0Requested, amount1Requested, owner):
        return self._contract.functions.collect(recipient,tickLower,tickUpper,amount0Requested,amount1Requested).call({'from': owner})



   # CUSTOM PROPERTIES
    @property
    def block(self)->int:
        return self._block
    @block.setter
    def block(self, value:int):
        # set block 
        self._block = value
        self.token0.block = value
        self.token1.block = value


   # CUSTOM FUNCTIONS
    def position(self, ownerAddress:str, tickLower:int, tickUpper:int)->dict:
        return self.positions(self.get_positionKey(ownerAddress=ownerAddress, tickLower=tickLower, tickUpper=tickUpper,))

    def get_rawPrices(self, tickUpper:int, tickLower:int)->dict:
        """ no decimal adjusted prices"""        
        priceCurrent = float(math.pow(1.0001, self.slot0["tick"]))
        priceUpper = float(math.pow(1.0001, tickUpper))
        priceLower = float(math.pow(1.0001, tickLower))
        return {"priceCurrent":priceCurrent,
                "priceUpper":priceUpper,
                "priceLower":priceLower
            }

    def get_tvlPriceFees(self, ownerAddress:str, tickUpper:int, tickLower:int)->dict:
        """ Calculate current TVL, price and uncollected fees, including owed, for each token in the pool

         Args:
            ownerAddress (str): address of the pool position owner
            tickUpper (int): 
            tickLower (int): 

         Returns:
            dict:  {"qtty_token0": ,
                    "qtty_token1": ,
                    "price_token0": ,
                    "price_token1": ,
                    "feesUncollected_token0": ,
                    "feesUncollected_token1": ,
                    "feesOwed_token0": ,
                    "feesOwed_token1": ,
                    }
         """        
        # get position data
        pos = self.position(ownerAddress=Web3.toChecksumAddress(ownerAddress.lower()),
            tickLower=tickLower,
            tickUpper=tickUpper,)

        # catch most used vars 
        decimals_token0 = self.token0.decimals
        decimals_token1 = self.token1.decimals
        
        # get decimal difference btween tokens
        decimal_diff = decimals_token1-decimals_token0
        
        # Tick PRICEs
        # calc tick prices (not decimal adjusted)
        prices = self.get_rawPrices(tickUpper, tickLower)
        # prepare price related vars 
        prices_sqrt = dict()
        prices_adj = dict()
        for k,v in prices.items():
            # Square root prices 
            prices_sqrt[k] = math.sqrt(v)
            # adjust decimals and reverse bc price in Uniswap is defined to be equal to token1/token0
            prices_adj[k] = 1/(v/ math.pow(10, decimal_diff))
        
        # TVL
        if (prices["priceCurrent"] <= prices["priceLower"]):
            amount0 = float(pos["liquidity"] * float(1 / prices_sqrt["priceLower"] - 1 / prices_sqrt["priceUpper"]))
            amount1 = 0
        elif (prices["priceCurrent"] < prices["priceUpper"]):
            amount0 = float(pos["liquidity"] * float(1 / prices_sqrt["priceCurrent"] - 1 / prices_sqrt["priceUpper"]))
            amount1 = float(pos["liquidity"] * float(prices_sqrt["priceCurrent"] - prices_sqrt["priceLower"]))
        else:
            amount1 = float(pos["liquidity"] * float(prices_sqrt["priceUpper"] - prices_sqrt["priceLower"]))
            amount0 = 0
        
        amount0 = amount0 / math.pow(10, float(decimals_token0))
        amount1 = amount1 / math.pow(10, float(decimals_token1))

        # UNCOLLECTED FEES  
        ticks_lower = self.ticks(tickLower)
        ticks_upper = self.ticks(tickUpper)
        # token0 fee
        feeGrowthOutside0X128_lower = ticks_lower["feeGrowthOutside0X128"]
        feeGrowthOutside0X128_upper = ticks_upper["feeGrowthOutside0X128"]
        feeGrowthInside0LastX128 = pos["feeGrowthInside0LastX128"]
        fees0 = ((self.feeGrowthGlobal0X128 - feeGrowthOutside0X128_lower - feeGrowthOutside0X128_upper - feeGrowthInside0LastX128)/_x128)*pos["liquidity"]/(10**decimals_token0)
        # token1 fee
        feeGrowthOutside1X128_lower = ticks_lower["feeGrowthOutside1X128"]
        feeGrowthOutside1X128_upper = ticks_upper["feeGrowthOutside1X128"]
        feeGrowthInside1LastX128 = pos["feeGrowthInside1LastX128"]
        fees1 = ((self.feeGrowthGlobal1X128 - feeGrowthOutside1X128_lower - feeGrowthOutside1X128_upper - feeGrowthInside1LastX128)/_x128)*pos["liquidity"]/(10**decimals_token1)
        ################################################################################################
        # TODO: I can't seem to get both tokens POSITIVE uncollected fees. Ive tried ... CHANGE THIS ASAP
        if fees0 < 0 :
            fees0 = 0
        if fees1 < 0 :
            fees1 = 0
        #################################################################################################



        # OWED FEES
        tokensOwed0 = pos["tokensOwed0"] / (10**decimals_token0)
        tokensOwed1 = pos["tokensOwed1"] / (10**decimals_token1)

        # retur result
        return {"qtty_token0": amount0,
                "qtty_token1": amount1,
                "price_token0": prices["priceCurrent"]/math.pow(10, decimal_diff),
                "price_token1": prices_adj["priceCurrent"],
                "fees_uncollected_token0": fees0,
                "fees_uncollected_token1": fees1,
                "fees_owed_token0": tokensOwed0,
                "fees_owed_token1": tokensOwed1,
            }
        

   # HELPERS
    def get_positionKey(self, ownerAddress:str, tickLower:int, tickUpper:int):
        """ 

         Args:
            ownerAddress (_type_): position owner wallet address
            tickLower (_type_): lower tick
            tickUpper (_type_): upper tick

         Returns:
            _type_: position key 
         """        
        val_types = ["address","int24","int24"]
        values =[ownerAddress,tickLower,tickUpper]
        return Web3.solidityKeccak(val_types, values).hex()



# PROTOCOLS
class gamma_hypervisor(erc20):
    _abi_filename = "hypervisor"
    _abi_path = "data/abi/gamma"

    _pool:univ3_pool = None

    _token0:erc20 = None
    _token1:erc20 = None

   # GRAL
    @property
    def baseLower(self):
        return self._contract.functions.baseLower().call(block_identifier=self.block)

    @property
    def baseUpper(self):
        return self._contract.functions.baseUpper().call(block_identifier=self.block)

    @property
    def currentTick(self)->int:
        return self._contract.functions.currentTick().call(block_identifier=self.block)
    
    @property
    def deposit0Max(self)->float:
        return self._contract.functions.deposit0Max().call(block_identifier=self.block)

    @property
    def deposit1Max(self)->float:
        return self._contract.functions.deposit1Max().call(block_identifier=self.block)

    @property
    def directDeposit(self)->bool:
        return self._contract.functions.directDeposit().call(block_identifier=self.block)

    @property
    def fee(self)->int:
        if not "fee" in self._cache:
            self._cache["fee"] = self._contract.functions.fee().call(block_identifier=self.block)
        return self._cache["fee"]

    @property
    def getBasePosition(self)->dict:
        """
         Returns:
            dict:   { 
                liquidity   28.7141300490401993
                amount0     72.329994
                amount1     56.5062023318300677907
                }
         """
        tmp =  self._contract.functions.getBasePosition().call(block_identifier=self.block)
        return {    "liquidity":tmp[0],
                    "amount0":tmp[1]/(10**self.token0.decimals),
                    "amount1":tmp[2]/(10**self.token1.decimals),
                }
    
    @property
    def getLimitPosition(self)->dict:
        """
         Returns:
            dict:   { 
                liquidity   28.7141300490401993
                amount0     72.329994
                amount1     56.5062023318300677907
                }
         """
        tmp = self._contract.functions.getLimitPosition().call(block_identifier=self.block)
        return {    "liquidity":tmp[0],
                    "amount0":tmp[1]/(10**self.token0.decimals),
                    "amount1":tmp[2]/(10**self.token1.decimals),
                }
    
    @property
    def getTotalAmounts(self)->dict:
        """ _

         Returns:
            _type_: total0   2.902086313
                    total1  56.5062023318300678136
         """
        tmp = self._contract.functions.getTotalAmounts().call(block_identifier=self.block)
        return {"total0":tmp[0]/(10**self.token0.decimals),
                "total1":tmp[1]/(10**self.token1.decimals),
                }
    
    @property
    def limitLower(self):
        return self._contract.functions.limitLower().call(block_identifier=self.block)
    
    @property
    def limitUpper(self):
        return self._contract.functions.limitUpper().call(block_identifier=self.block)
    
    @property
    def maxTotalSupply(self)->int:
        return self._contract.functions.maxTotalSupply().call(block_identifier=self.block)/(10**self.decimals)

    @property
    def name(self)->str:
        if not "name" in self._cache:
            self._cache["name"] = self._contract.functions.name().call(block_identifier=self.block)
        return self._cache["name"]

    def nonces(self, owner:str):
        return self._contract.functions.nonces()(Web3.toChecksumAddress(owner)).call(block_identifier=self.block)

    @property
    def owner(self)->str:
        return self._contract.functions.owner().call(block_identifier=self.block)

    @property
    def pool(self)->str:
        if self._pool == None:
            self._pool = univ3_pool(address=self._contract.functions.pool().call(block_identifier=self.block), web3Provider=self._w3)
        return self._pool

    @property
    def tickSpacing(self)->int:
        return self._contract.functions.tickSpacing().call(block_identifier=self.block)

    @property
    def token0(self)->erc20:
        if self._token0 == None:
            self._token0 = erc20(address=self._contract.functions.token0().call(block_identifier=self.block),
                                 web3Provider=self._w3)
        return self._token0
    
    @property
    def token1(self)->erc20:
        if self._token1 == None:
            self._token1 = erc20(address=self._contract.functions.token1().call(block_identifier=self.block),
                                 web3Provider=self._w3)
        return self._token1
    
    @property
    def witelistedAddress(self)->str:
        return self._contract.functions.witelistedAddress().call(block_identifier=self.block)

   # CUSTOM PROPERTIES
    @property
    def block(self):
        """ """
        return self._block

    @block.setter
    def block(self, value):
        self._block = value
        self.pool.block = value
        self.token0.block = value
        self.token1.block = value


   # CUSTOM FUNCTIONS
    def tvl_price_fee(self)->dict:
        """ Return Value locked, prices, uncollected and owed fees 

        Returns:
            dict: {"qtty_token0": ,
                    "qtty_token1": ,
                    "price_token0": ,
                    "price_token1": ,
                    "feesUncollected_token0": ,
                    "feesUncollected_token1": ,
                    "feesOwed_token0": ,
                    "feesOwed_token1": ,
                    }
        """      
        # UNISWAP positions  
        result = self.pool.get_tvlPriceFees(ownerAddress=self.address, tickUpper=self.baseUpper, tickLower=self.baseLower)
        limit = self.pool.get_tvlPriceFees(ownerAddress=self.address, tickUpper=self.limitUpper, tickLower=self.limitLower)
        # sumup position keys
        for k in result.keys():
            if not k in ["price_token0","price_token1"]:
                result[k] += limit[k]
            else:
                result[k] += limit[k]
                result[k] /= 2

        # CONTRACT parked tokens (tvl)
        qttyParked_token0 = self.pool.token0.balanceOf(self.address)
        qttyParked_token1 = self.pool.token1.balanceOf(self.address)
        result["qtty_token0"] += qttyParked_token0
        result["qtty_token1"] += qttyParked_token1

        # return result
        return result
