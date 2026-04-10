# Bug Report: BH-1042

**Title:** Customer overcharged on tax when discount code is applied

**Severity:** High  
**Reporter:** jane.nguyen@acme.com  
**Date:** 2026-04-07  
**Component:** Order Processing / Checkout  

## Description

Multiple customers have reported that the total charged on discounted orders is higher than
expected. When a discount code is applied at checkout, the final total does not match what
customers calculate manually. The tax amount appears to be too high.

## Expected Behavior

When a 20% discount is applied to a $200.00 order:
- Subtotal: $200.00
- Discount (20%): -$40.00
- Discounted subtotal: $160.00
- Tax (8%): **$12.80** (8% of $160.00)
- **Total: $172.80**

## Actual Behavior

The system charges:
- Subtotal: $200.00
- Discount (20%): -$40.00
- Discounted subtotal: $160.00
- Tax (8%): **$16.00** (appears to be 8% of the ORIGINAL $200.00)
- **Total: $176.00**

The customer is overcharged by $3.20 in this example.

## Environment

- **Language/Runtime:** Python 3.11
- **OS:** Ubuntu 22.04 (production), macOS 14 (dev)
- **Module:** `src/order_processor.py` → `OrderProcessor.calculate_total()`
- **Deploy version:** v2.14.3 (deployed 2026-04-05)

## Steps to Reproduce (Partial)

1. Create an order with items totaling $200.00
2. Apply discount code `SAVE20`
3. Call `calculate_total()`
4. Observe that `tax` field is $16.00 instead of $12.80

## Additional Context

- Issue appeared after v2.14.3 deploy on April 5th.
- No discount-related code was intentionally changed in that release.
- Affects all discount codes, not just SAVE20.
- Approximately 340 affected orders in the past 48 hours.
- Finance team is asking for a resolution ASAP for refund calculations.
