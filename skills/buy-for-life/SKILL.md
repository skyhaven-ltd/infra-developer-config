---
name: buy-for-life
description: Recommend durable, repairable, good-value products to purchase in the UK using live UK prices, availability, evidence, long-term owner reviews, reputable brands, warranties, parts availability, independent testing, and price-aware tradeoffs. Use for UK buy-it-for-life, product comparison, purchase advice, replacement research, best value, budget-aware durability, or avoiding low-quality products.
---

# Buy For Life

Use this skill to recommend products available to buy in the UK that are likely to last and make economic sense for the user's budget. "Best" means best fit for the user's constraints, not the most expensive technically superior option.

## Workflow

1. Clarify the job:
   - Identify the product category, budget range, must-have features, deal breakers, usage intensity, storage limits, repair tolerance, and aesthetic or compatibility constraints.
   - Assume the buyer is in the UK. Ask one concise question if budget or product category is unclear. Otherwise state assumptions and proceed.

2. Gather current evidence:
   - Browse the web for current UK prices, UK stock availability, UK model variants, UK warranty terms, recalls, and recent owner reports.
   - Prefer primary or reputable sources: manufacturer specifications, parts catalogs, warranty terms, Consumer Reports or equivalent independent testing, Wirecutter-style long-term testing, iFixit or repair documentation, trade forums, specialist retailers, and long-running owner communities.
   - Prefer UK sources for price and availability: manufacturer UK sites, authorised UK retailers, UK repairers, UK parts suppliers, Which?, Expert Reviews, Auto Express, Trusted Reviews, and UK owner forums where relevant.
   - Treat affiliate listicles, SEO review farms, unverified social posts, and sponsored rankings as weak signals.
   - Look for multi-year ownership evidence, common failure modes, spare parts, repairability, warranty behavior, and total cost over time.

3. Evaluate tradeoffs:
   - Score candidates on durability, repairability, availability, warranty support, parts ecosystem, performance for the intended use, and value.
   - Penalize products that are excellent but poor value unless the user's use case justifies the premium.
   - Include budget picks when they are honest compromises, even if they are not true lifetime purchases.
   - Avoid recommending discontinued, UK-unavailable, grey-import, or currently overpriced products unless clearly labeled.

4. Recommend:
   - Rank products by fit, not prestige.
   - Put the best value durable option first when it is close to the best overall option at a much lower price.
   - Include "buy", "consider if", and "avoid" guidance when the category has traps.
   - Name evidence quality and uncertainty plainly.

## Output

Default to this structure:

```markdown
Best pick: [product]
[1-2 sentences on why it fits the user's constraints]

Also consider:
- [product]: [when it is better]
- [product]: [budget or premium tradeoff]

Avoid:
- [product/type]: [reason]

Evidence notes:
- [key sources or evidence types used]
- [important uncertainty, if any]
```

Always use live browsing where possible and include links to sources used. If live browsing is unavailable, say so and give a UK-focused research checklist instead of pretending recommendations are current.
