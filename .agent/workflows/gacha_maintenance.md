---
description: How to adjust Gacha and Economy balance
---
# Gacha and Economy Balance Workflow

This workflow describes how to adjust the economy and gacha rates.

## 1. Adjusting Gacha Rates
File: `utils/cogs/game/const.py`
Locate `GACHA_RARITY_TIERS`.
- `weight`: The probability weight. Higher = more common.
- Total probability for a tier = `tier_weight / sum(all_weights)`

## 2. Adjusting Gacha Cost
File: `utils/cogs/game/const.py`
Locate `GACHA_COST`.
- Currently set to `250`.

## 3. Adjusting Work/Job Rewards
File: `data/commands/minigames/grounded.json`
- `base_reward`: Range `[min, max]` of Stella Points.
- `pay_range`: For specific jobs.

## 4. Adjusting Cooldowns and Max Uses
File: `utils/cogs/game/const.py`
Locate `TIMER_CONFIG`.
- `max_uses`: How many times a command can be used in the cooldown period.
- `cooldown`: Time in seconds before uses reset.

## 5. Adjusting Work Failure Rates
File: `utils/cogs/game/view.py`
- Look for `work_command` or `WorkTaskView`.
- Adjust `random.random() < 0.10` (10%) for failure chance.
