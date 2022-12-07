const superagent = require('superagent');
const { request, gql } = require('graphql-request');
const sdk = require('@defillama/sdk');

const utils = require('../utils');



const CHAINS = {
    ethereum: 'gamma',
    optimism: 'optimism',
    polygon: 'polygon',
    arbitrum: 'arbitrum',
    celo: 'celo'
  };
  
  
  const CHAIN_IDS = {
    ethereum: 1,
    optimism: 10,
    polygon: 137,
    arbitrum: 42161,
    celo: 42220
  };


const getUrl = (chain) =>
`https://api.thegraph.com/subgraphs/name/gammastrategies/${chain}`;

const hypervisorsQuery = gql`
{
    uniswapV3Hypervisors(where: {  tvl0_gt: "0", totalSupply_gt: "0"}) {
      id
      symbol
      created
      pool {
        token0 {
          symbol
          id
          decimals
        }
        token1 {
          symbol
          id
          decimals
        }
        fee
      }
      rebalances(orderBy: timestamp, orderDirection: desc, first: 100) {
        timestamp
        totalAmountUSD
        grossFeesUSD
      }
  
    }
  }
`;

const getSumByKey = (arr, key) => {
    return arr.reduce((accumulator, current) => accumulator + Number(current[key]), 0)
  }
const pairsToObj = (pairs) =>
  pairs.reduce((acc, [el1, el2]) => ({ ...acc, [el1]: el2 }), {});

const getApy = async () => {
  const hypervisorsDta = pairsToObj(
    await Promise.all(
      Object.keys(CHAINS).map(async (chain) => [
        chain,
        await request(getUrl(CHAINS[chain]), hypervisorsQuery),
      ])
    )
  );

  const tokens = Object.entries(hypervisorsDta).reduce(
    (acc, [chain, { uniswapV3Hypervisors }]) => ({
      ...acc,
      [chain]: [
        ...new Set(
            uniswapV3Hypervisors
            .map((hypervisor) => [hypervisor.pool.token0.id, hypervisor.pool.token1.id])
            .flat()
        ),
      ],
    }),
    {}
  );

  const keys = [];
  for (const key of Object.keys(tokens)) {
    keys.push(tokens[key].map((t) => `${key}:${t}`));
  }
  const prices = (
    await superagent.post('https://coins.llama.fi/prices').send({
      coins: keys.flat(),
    })
  ).body.coins;

  const pools = Object.keys(CHAINS).map((chain) => {
    const { uniswapV3Hypervisors: chainHypervisors } = hypervisorsDta[chain];
    
    const chainAprs = chainHypervisors.filter(function(hyp) {
        if (hyp.rebalances.length>1) {
          return true;
        }
        return false;
      }).map((hypervisor) => {
      
      const aggregatedtvl = getSumByKey(hypervisor.rebalances, 'totalAmountUSD');
      const aggregatedfees = getSumByKey(hypervisor.rebalances, 'grossFeesUSD');
      const secs_passed = hypervisor.rebalances[0].timestamp-hypervisor.rebalances[hypervisor.rebalances.length-1].timestamp;
      const averageTVL = ((aggregatedtvl > aggregatedfees) ? (aggregatedtvl-aggregatedfees)/hypervisor.rebalances.length : aggregatedtvl/hypervisor.rebalances.length);

      const yearlyFees = ((aggregatedfees/secs_passed)*(60*60*24*365))
      const apr = yearlyFees/averageTVL

      return {
        pool: hypervisor.id,
        chain: utils.formatChain(chain),
        project: 'visor',
        symbol: `${hypervisor.pool.token0.symbol}-${hypervisor.pool.token1.symbol}`,
        tvlUsd: averageTVL || 0,
        apyBase: apr || 0,
        underlyingTokens: [hypervisor.pool.token0.id, hypervisor.pool.token1.id],
        poolMeta: `${hypervisor.pool.fee/1000} univ3 pool`,
      };
    });
    return chainAprs;
  });
  return pools.flat();
};

module.exports = {
    timetravel: false,
    apy: getApy,
    url: 'https://app.gamma.xyz/dashboard',
  };
