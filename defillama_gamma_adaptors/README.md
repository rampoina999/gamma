DefiLlama APY Server: (main page https://github.com/DefiLlama/yield-server)
Requirements:  data sourced from subgraph's or on-chain calls. Private API on special ocasions

GAMMA version 1
Folder: visor_v1
Description:
  All values are sourced from subgraph data.
  APR formulas are as follows:
    data used = last 100 rebalances per hypevisor
    <aggregated fees> = sum of rebalances <grossFeesUSD> field
    <aggregated tvl> = sum of rebalances <totalAmountUSD> field
    <time_passed> = time passed between last and first rebalance in the list 
    <average TVL> = <aggregated tvl> minus <aggregated fees> divided by total number of rebalances
      when <aggregated tvl> is lower than <aggregated fees>, do not make the substraction
    <yearly fees> = <aggregated fees> divided by <time_passed> and extrapolated to whole year

    <APR> = <yearly fees> divided by <average TVL>


    
GAMMA version 2
Folder: visor_v2
Description:
  Values sourced from 
      subgraph: Hypervisor addresses and TVL
      private API: https://gammawire.net/hypervisors/returns    apy
  
      
   
