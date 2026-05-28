{{ config(materialized='view') }}

with source_data as (

    select *
    from {{ source('raw_crypto', 'funding_raw') }}

),

cleaned as (

    select
        lower(cast(exchange as string)) as exchange,
        upper(cast(symbol as string)) as symbol,

        safe_cast(timestamp as timestamp) as observed_at,
        safe_cast(date as date) as observed_date,

        safe_cast(mark_price as float64) as mark_price,
        safe_cast(spot_price as float64) as spot_price,
        safe_cast(basis_spread as float64) as basis_spread,
        safe_cast(basis_pct as float64) as basis_pct,

        safe_cast(funding_rate_coin as float64) as funding_rate_coin,
        safe_cast(funding_rate_usdt as float64) as funding_rate_usdt,

        safe_cast(annualized_funding_coin as float64) as annualized_funding_coin,
        safe_cast(annualized_funding_usdt as float64) as annualized_funding_usdt,
        safe_cast(annualized_basis_coin as float64) as annualized_basis_coin,
        safe_cast(annualized_basis_usdt as float64) as annualized_basis_usdt,
        safe_cast(arbitrage_spread as float64) as arbitrage_spread,

        safe_cast(next_funding_time as float64) as next_funding_time,

        lower(cast(funding_regime as string)) as funding_regime,
        upper(cast(arbitrage_opportunity as string)) as arbitrage_opportunity,
        safe_cast(leverage_stress as float64) as leverage_stress,

        cast(source as string) as source,
        cast(run_id as string) as run_id,
        safe_cast(ingestion_time as timestamp) as ingestion_time,

        cast(year as string) as year,
        cast(month as string) as month,
        cast(day as string) as day

    from source_data

),

deduped as (

    select
        *,
        row_number() over (
            partition by exchange, symbol, observed_at
            order by ingestion_time desc, run_id desc
        ) as rn
    from cleaned
    where symbol in ('BTC', 'ETH')
      and exchange is not null
      and observed_at is not null
      and mark_price > 0
      and spot_price > 0
      and basis_pct between -20 and 20
      and funding_rate_coin between -10 and 10
      and funding_rate_usdt between -10 and 10

)

select * except(rn)
from deduped
where rn = 1