# Manafold CAP miner: bootstrap experiment

Generated: 2026-09-24T06:30:30.527011+00:00 UTC

## Dataset inventory

### scryfall: `nishtahir/scryfall-oracle-cards`

Revision: `0ce026779dae1a9a6448ef7a85e606d662343f5e`. Rows: **36,923**. Splits: `{'train': 36923}`.

Columns: `reprint`, `all_parts`, `textless`, `rulings_uri`, `flavor_text`, `image_uris`, `set_id`, `card_faces`, `power`, `life_modifier`, `set_search_uri`, `watermark`, `artist`, `tcgplayer_id`, `cmc`, `oracle_id`, `edhrec_rank`, `content_warning`, `set_type`, `loyalty`, `flavor_name`, `nonfoil`, `preview`, `attraction_lights`, `collector_number`, `game_changer`, `highres_image`, `keywords`, `oracle_text`, `games`, `resource_id`, `set_name`, `released_at`, `uri`, `digital`, `frame_effects`, `id`, `security_stamp`, `prices`, `colors`, `multiverse_ids`, `color_identity`, `scryfall_set_uri`, `type_line`, `variation`, `reserved`, `purchase_uris`, `printed_type_line`, `lang`, `border_color`, `toughness`, `defense`, `name`, `layout`, `color_indicator`, `object`, `set`, `related_uris`, `illustration_id`, `foil`, `legalities`, `booster`, `story_spotlight`, `rarity`, `oversized`, `hand_modifier`, `finishes`, `frame`, `prints_search_uri`, `mtgo_foil_id`, `card_back_id`, `set_uri`, `scryfall_uri`, `produced_mana`, `promo_types`, `mana_cost`, `arena_id`, `mtgo_id`, `artist_ids`, `cardmarket_id`, `image_status`, `promo`, `penny_rank`, `tcgplayer_etched_id`, `full_art`, `printed_text`

### forge: `404NotF0und/MtG-json-to-ForgeScript`

Revision: `cef86f363d7f7d5b3293248a75f550a7c3404066`. Rows: **27,286**. Splits: `{'train': 19100, 'validation': 2729, 'test': 5457}`.

Columns: `instruction`, `input`, `output`, `text`

### xmage: `Frogski/xMageData`

Revision: `6212eb37907c1ce751d8a3fea8b3322056dc0264`. Rows: **18,985**. Splits: `{'train': 18985}`.

Columns: `prompt`, `completion`

Dataset loading used `datasets`; repository revisions were queried with `huggingface_hub`. Local package versions: `{'datasets': '5.0.1', 'huggingface_hub': '1.32.0', 'PyYAML': '6.0.3'}`. Inventory generation/cache retrieval timestamp: `2026-09-24T06:30:06.364610+00:00` UTC. Rows were materialized from Hugging Face cache at `data/raw/hf`.

## Matching

Scryfall Oracle rows: 36,923; Forge records: 27,286; XMage records: 18,985.
Forge records matched: 26,384; distinct Oracle identities with Forge: 26,384 (71.46%).
XMage records matched: 18,273; distinct Oracle identities with XMage: 18,260 (49.45%).
Both: 17,270 (46.77%); unmatched Forge: 48; unmatched XMage: 55; ambiguous records: 1,511.
Normalized Oracle-text comparison after name matching: `{'forge': {'MATCH': 12975, 'MISMATCH': 12380, 'MISSING': 1029}, 'xmage': {'MISMATCH': 9518, 'MATCH': 8536, 'MISSING': 219}}`. `MISMATCH` is diagnostic (it can indicate stale text, templating differences, or a bad match), not a silently rejected join.

Matching tries Oracle ID, normalized exact name (including face names), then normalized name plus normalized Oracle text. It does not fuzzy-match. Records with multiple exact-name candidates are retained as ambiguous.

## Forge vocabulary

Action frequencies are in `data/output/forge_tokens.csv`; `$` field vocabulary is in `inventory.json`. The parser inventories observed action names rather than constraining them to a closed list. Top actions:

| token | count |
|---|---:|
| `ChangesZone` | 5519 |
| `ChangeZone` | 5242 |
| `Continuous` | 4112 |
| `Pump` | 4112 |
| `Draw` | 2706 |
| `Token` | 2581 |
| `DealDamage` | 2356 |
| `Cleanup` | 2346 |
| `PutCounter` | 2151 |
| `Mana` | 1902 |
| `Phase` | 1799 |
| `Effect` | 1422 |
| `GainLife` | 1409 |
| `Attach` | 1315 |
| `Destroy` | 1302 |
| `Attacks` | 1095 |
| `SpellCast` | 1013 |
| `LoseLife` | 932 |
| `Animate` | 870 |
| `Discard` | 866 |
| `PumpAll` | 839 |
| `Dig` | 736 |
| `DamageDone` | 695 |
| `Sacrifice` | 692 |
| `Tap` | 685 |
| `ChangeZoneAll` | 575 |
| `Charm` | 516 |
| `Counter` | 466 |
| `Mill` | 430 |
| `Scry` | 413 |
| `ChooseCard` | 406 |
| `Untap` | 405 |
| `DelayedTrigger` | 400 |
| `ReduceCost` | 373 |
| `RepeatEach` | 366 |
| `DamageAll` | 363 |
| `DestroyAll` | 319 |
| `CantBlockBy` | 316 |
| `SetState` | 290 |
| `GainControl` | 283 |

Top Forge `$` fields:

| token | count |
|---|---:|
| `DB` | 56864 |
| `Mode` | 40984 |
| `SpellDescription` | 38427 |
| `Cost` | 32158 |
| `Execute` | 26752 |
| `TriggerDescription` | 25994 |
| `Defined` | 25891 |
| `ValidTgts` | 24726 |
| `SubAbility` | 23496 |
| `Destination` | 23332 |
| `Origin` | 22727 |
| `ValidCard` | 20812 |
| `AB` | 20062 |
| `TgtPrompt` | 17920 |
| `SP` | 15098 |
| `TriggerZones` | 13329 |
| `Description` | 12884 |
| `Affected` | 8315 |
| `NumCards` | 6716 |
| `Ability` | 6645 |
| `AILogic` | 5707 |
| `NumDmg` | 5468 |
| `NumAtt` | 5432 |
| `Type` | 5401 |
| `CounterType` | 5223 |
| `TokenScript` | 5184 |
| `Count` | 4955 |
| `LifeAmount` | 4794 |
| `CounterNum` | 4738 |
| `Phase` | 4403 |
| `StackDescription` | 4353 |
| `ValidCards` | 4325 |
| `ChangeType` | 4241 |
| `ValidPlayer` | 4227 |
| `KW` | 4202 |
| `ClearRemembered` | 4138 |
| `TokenAmount` | 3972 |
| `ChangeNum` | 3925 |
| `NumDef` | 3912 |
| `Produced` | 3816 |

## XMage vocabulary

Java imports and class-like vocabulary are extracted lexically, not parsed as Java. Top classes:

| token | count |
|---|---:|
| `SimpleActivatedAbility` | 3639 |
| `SimpleStaticAbility` | 3453 |
| `OneShotEffect` | 3299 |
| `TargetCreaturePermanent` | 2845 |
| `EntersBattlefieldTriggeredAbility` | 2251 |
| `FlyingAbility` | 2186 |
| `TapSourceCost` | 2044 |
| `TargetPermanent` | 1983 |
| `FilterPermanent` | 1718 |
| `FilterCreaturePermanent` | 1696 |
| `CreateTokenEffect` | 1441 |
| `TargetController` | 1298 |
| `DrawCardSourceControllerEffect` | 1277 |
| `FilterCard` | 1231 |
| `GenericManaCost` | 1204 |
| `FilterControlledPermanent` | 978 |
| `DamageTargetEffect` | 955 |
| `AddCountersSourceEffect` | 873 |
| `BoostSourceEffect` | 827 |
| `BoostTargetEffect` | 825 |
| `TrampleAbility` | 820 |
| `AttachEffect` | 761 |
| `EnchantAbility` | 744 |
| `DestroyTargetEffect` | 728 |
| `TargetControlledCreaturePermanent` | 720 |
| `GainLifeEffect` | 717 |
| `GainAbilityTargetEffect` | 713 |
| `HasteAbility` | 688 |
| `SacrificeTargetCost` | 669 |
| `SacrificeSourceCost` | 631 |
| `TargetCardInYourGraveyard` | 622 |
| `BeginningOfUpkeepTriggeredAbility` | 611 |
| `FixedTarget` | 608 |
| `TargetPlayer` | 577 |
| `TargetControlledPermanent` | 568 |
| `GainAbilitySourceEffect` | 549 |
| `TargetCardInLibrary` | 545 |
| `FilterControlledCreaturePermanent` | 530 |
| `VigilanceAbility` | 508 |
| `TargetAnyTarget` | 508 |

## Cross-engine evidence

Requirement candidate counts by implementation evidence: `{'UNRESOLVED': 15408, 'FORGE_ONLY': 8925, 'MULTI_IMPLEMENTATION_AGREEMENT': 2962, 'XMAGE_ONLY': 2199}`. `MULTI_IMPLEMENTATION_AGREEMENT` means both implementations have extracted constructs that the seed map assigns to the same generic candidate. It is corroboration only: all candidates remain `rules_evidence: NOT_CHECKED` and `review_status: UNREVIEWED`. `CONFLICT` is not inferred from different mapped effects on one card because cards commonly contain multiple effects, and this pass has no rule-aware contradiction detector.

## Examples and data quality

Machine-readable records retain Oracle text, Forge input/action snippets, and XMage prompt/import/constructor excerpts needed to audit extraction. The report includes review samples below. Scryfall has one row per Oracle ID in this revision. Forge and XMage examples are generated implementation data; mismatched or stale text is possible. Face-name joins can associate a face with its parent card identity. No malformed records were silently repaired.

### Simple successful examples

- `Sensory Deprivation` — Oracle: Enchant creature
Enchanted creature gets -3/-0. Forge: `Attach, Continuous`; XMage: `AttachEffect, BoostEnchantedEffect, EnchantAbility, SimpleStaticAbility, TargetCreaturePermanent`. Raw Forge: `A:SP$ Attach | Cost$ U | ValidTgts$ Creature | AILogic$ Curse`. Raw XMage: `import mage.abilities.common.SimpleStaticAbility; import mage.abilities.effects.common.AttachEffect; import mage.abilities.effects.common.continuous.B`.
- `Walking Sponge` — Oracle: {T}: Target creature loses your choice of flying, first strike, or trample until end of turn. Forge: `Animate, GenericChoice, Pump`; XMage: `ContinuousEffect, FirstStrikeAbility, FlyingAbility, LoseAbilityTargetEffect, OneShotEffect`. Raw Forge: `A:AB$ Pump | Cost$ T | ValidTgts$ Creature | TgtPrompt$ Select target creature | StackDescription$ None | SubAbility$ MakeChoice | SpellDescription$ T`. Raw XMage: `import mage.abilities.Ability; import mage.abilities.common.SimpleActivatedAbility; import mage.abilities.costs.common.TapSourceCost; import mage.abil`.
- `Ravnica at War` — Oracle: Exile all multicolored permanents. Forge: `ChangeZoneAll`; XMage: `ExileAllEffect, FilterPermanent`. Raw Forge: `A:SP$ ChangeZoneAll | Cost$ 3 W | ChangeType$ Permanent.MultiColor | Origin$ Battlefield | Destination$ Exile | SpellDescription$ Exile all multicolor`. Raw XMage: `import mage.abilities.effects.common.ExileAllEffect; import mage.filter.FilterPermanent; import mage.filter.predicate.mageobject.MulticoloredPredicate`.
- `Wyluli Wolf` — Oracle: {T}: Target creature gets +1/+1 until end of turn. Forge: `Pump`; XMage: `BoostTargetEffect, SimpleActivatedAbility, TapSourceCost, TargetCreaturePermanent`. Raw Forge: `A:AB$ Pump | Cost$ T | ValidTgts$ Creature | TgtPrompt$ Select target creature | NumAtt$ +1 | NumDef$ +1 | SpellDescription$ Target creature gets +1/+`. Raw XMage: `import mage.abilities.Ability; import mage.abilities.common.SimpleActivatedAbility; import mage.abilities.costs.common.TapSourceCost; import mage.abil`.
- `Nantuko Elder` — Oracle: {T}: Add {C}{G}. Forge: `Mana`; XMage: `SimpleManaAbility, TapSourceCost`. Raw Forge: `A:AB$ Mana | Cost$ T | Produced$ C G | SpellDescription$ Add {C}{G}.`. Raw XMage: `import mage.abilities.costs.common.TapSourceCost; import mage.abilities.mana.SimpleManaAbility; this.addAbility(new SimpleManaAbility(Zone.BATTLEFIELD`.
- `Vedalken Heretic` — Oracle: Whenever this creature deals damage to an opponent, you may draw a card. Forge: `DamageDone, Draw`; XMage: `DealsDamageToOpponentTriggeredAbility, DrawCardSourceControllerEffect`. Raw Forge: `T:Mode$ DamageDone | ValidSource$ Card.Self | ValidTarget$ Opponent | OptionalDecider$ You | Execute$ TrigDraw | TriggerDescription$ Whenever CARDNAME`. Raw XMage: `import mage.abilities.common.DealsDamageToOpponentTriggeredAbility; import mage.abilities.effects.common.DrawCardSourceControllerEffect; this.addAbili`.
- `Palinchron` — Oracle: Flying
When this creature enters, untap up to seven lands.
{2}{U}{U}: Return this creature to its owner's hand. Forge: `ChangeZone, ChangesZone, Untap`; XMage: `EntersBattlefieldTriggeredAbility, FlyingAbility, ReturnToHandSourceEffect, SimpleActivatedAbility, UntapLandsEffect`. Raw Forge: `T:Mode$ ChangesZone | ValidCard$ Card.Self | Origin$ Any | Destination$ Battlefield | Execute$ TrigUntap | TriggerDescription$ When CARDNAME enters th`. Raw XMage: `import mage.abilities.common.EntersBattlefieldTriggeredAbility; import mage.abilities.common.SimpleActivatedAbility; import mage.abilities.costs.mana.`.
- `Disposal Mummy` — Oracle: When this creature enters, exile target card from an opponent's graveyard. Forge: `ChangeZone, ChangesZone`; XMage: `EntersBattlefieldTriggeredAbility, ExileTargetEffect, FilterCard, TargetCardInOpponentsGraveyard`. Raw Forge: `T:Mode$ ChangesZone | Origin$ Any | Destination$ Battlefield | ValidCard$ Card.Self | Execute$ TrigExile | TriggerDescription$ When CARDNAME enters th`. Raw XMage: `import mage.abilities.Ability; import mage.abilities.common.EntersBattlefieldTriggeredAbility; import mage.abilities.effects.common.ExileTargetEffect;`.
- `Wei Strike Force` — Oracle: Horsemanship (This creature can't be blocked except by creatures with horsemanship.) Forge: ``; XMage: `HorsemanshipAbility`. Raw Forge: `no extracted action line`. Raw XMage: `import mage.abilities.keyword.HorsemanshipAbility;`.
- `Safewright Quest` — Oracle: Search your library for a Forest or Plains card, reveal it, put it into your hand, then shuffle. Forge: `ChangeZone`; XMage: `FilterCard, SearchLibraryPutInHandEffect, TargetCardInLibrary`. Raw Forge: `A:SP$ ChangeZone | Cost$ GW | Origin$ Library | Destination$ Hand | ChangeType$ Forest,Plains | ChangeNum$ 1 | SpellDescription$ Search your library f`. Raw XMage: `import mage.abilities.effects.common.search.SearchLibraryPutInHandEffect; import mage.filter.FilterCard; import mage.filter.predicate.Predicates; impo`.

### Interesting complex examples

- `Master of the Hunt` — Oracle excerpt: {2}{G}{G}: Create a 1/1 green Wolf creature token named Wolves of the Hunt. It has "bands with other creatures named Wolves of the Hunt." (Any creatures named Wolves of the Hunt ca Forge: `Token`; XMage: `CreateTokenEffect, SimpleActivatedAbility`. Raw Forge: `A:AB$ Token | Cost$ 2 G G | TokenAmount$ 1 | TokenScript$ wolves_of_the_hunt | TokenOwner$ You | SpellDescription$ Create a 1/1 green Wolf creature to`. Raw XMage: `import mage.abilities.common.SimpleActivatedAbility; import mage.abilities.costs.mana.ManaCostsImpl; import mage.abilities.effects.common.CreateTokenE`.
- `Dance of the Dead` — Oracle excerpt: Enchant creature card in a graveyard
When this Aura enters, if it's on the battlefield, it loses "enchant creature card in a graveyard" and gains "enchant creature put onto the bat Forge: `Animate, Attach, ChangeZone, ChangesZone, Cleanup, Continuous, DelayedTrigger, Destroy`; XMage: `AnimateDeadTriggeredAbility, AttachEffect, BeginningOfUpkeepTriggeredAbility, BoostEnchantedEffect, DanceOfTheDeadDoIfCostPaidEffect, DontUntapInControllersUntapStepEnchantedEffect, EnchantAbility, FilterCreatureCard`. Raw Forge: `A:SP$ Attach | Cost$ 1 B | ValidTgts$ Creature | TgtZone$ Graveyard | AILogic$ Reanimate`. Raw XMage: `import mage.abilities.Ability; import mage.abilities.Mode; import mage.abilities.common.AnimateDeadTriggeredAbility; import mage.abilities.common.Begi`.
- `Camouflage` — Oracle excerpt: Cast this spell only during your declare attackers step.
This turn, instead of declaring blockers, each defending player chooses any number of creatures they control and divides th Forge: `Camouflage, Effect`; XMage: `CamouflageEffect, CastOnlyDuringPhaseStepSourceAbility, FilterControlledCreaturePermanent, FilterCreaturePermanent, MyTurnCondition, TargetControlledCreaturePermanent`. Raw Forge: `A:SP$ Effect | Cost$ G | ReplacementEffects$ RDeclareBlocker | ActivationPhases$ Declare Attackers | PlayerTurn$ True | AILogic$ Evasion | SpellDescri`. Raw XMage: `import mage.abilities.Ability; import mage.abilities.common.CastOnlyDuringPhaseStepSourceAbility; import mage.abilities.condition.common.MyTurnConditi`.
- `Takklemaggot` — Oracle excerpt: Enchant creature
At the beginning of the upkeep of enchanted creature's controller, put a -0/-1 counter on that creature.
When enchanted creature dies, that creature's controller c Forge: `Animate, Attach, ChangeZone, ChangesZone, ChooseCard, Cleanup, DealDamage, Phase`; XMage: `AddCountersAttachedEffect, AttachEffect, BeginningOfUpkeepTriggeredAbility, DamageTargetEffect, DiesAttachedTriggeredAbility, EnchantAbility, FilterCreaturePermanent, FixedTarget`. Raw Forge: `A:SP$ Attach | Cost$ 2 B B | ValidTgts$ Creature | AILogic$ Curse`. Raw XMage: `import mage.abilities.Ability; import mage.abilities.TriggeredAbilityImpl; import mage.abilities.common.BeginningOfUpkeepTriggeredAbility; import mage`.
- `Necromancy` — Oracle excerpt: You may cast this spell as though it had flash. If you cast it any time a sorcery couldn't have been cast, the controller of the permanent it becomes sacrifices it at the beginning Forge: `Animate, Attach, ChangeZone, ChangesZone, Cleanup, DelayedTrigger, Destroy`; XMage: `AnimateDeadTriggeredAbility, CastAsThoughItHadFlashSourceEffect, FilterCreatureCard, SacrificeIfCastAtInstantTimeTriggeredAbility, SimpleStaticAbility, TargetCardInGraveyard`. Raw Forge: `T:Mode$ ChangesZone | Origin$ Any | Destination$ Battlefield | ValidCard$ Card.Self | Execute$ RaiseDead | TriggerDescription$ When CARDNAME enters th`. Raw XMage: `import mage.abilities.Ability; import mage.abilities.common.AnimateDeadTriggeredAbility; import mage.abilities.common.SacrificeIfCastAtInstantTimeTrig`.
- `Cathedral of Serra` — Oracle excerpt: White legendary creatures you control have "bands with other legendary creatures." (Any legendary creatures can attack in a band as long as at least one has "bands with other legen Forge: `Continuous`; XMage: `BandsWithOtherAbility, FilterCreaturePermanent, GainAbilityControlledEffect, SimpleStaticAbility`. Raw Forge: `S:Mode$ Continuous | Affected$ Creature.White+Legendary+YouCtrl | AddKeyword$ Bands with Other Legendary Creatures | Description$ White legendary crea`. Raw XMage: `import mage.abilities.common.SimpleStaticAbility; import mage.abilities.effects.common.continuous.GainAbilityControlledEffect; import mage.abilities.k`.
- `Adventurers' Guildhouse` — Oracle excerpt: Green legendary creatures you control have "bands with other legendary creatures." (Any legendary creatures can attack in a band as long as at least one has "bands with other legen Forge: `Continuous`; XMage: `BandsWithOtherAbility, FilterCreaturePermanent, GainAbilityControlledEffect, SimpleStaticAbility`. Raw Forge: `S:Mode$ Continuous | Affected$ Creature.Green+Legendary+YouCtrl | AddKeyword$ Bands with Other Legendary Creatures | Description$ Green legendary crea`. Raw XMage: `import mage.abilities.common.SimpleStaticAbility; import mage.abilities.effects.common.continuous.GainAbilityControlledEffect; import mage.abilities.k`.
- `Unholy Citadel` — Oracle excerpt: Black legendary creatures you control have "bands with other legendary creatures." (Any legendary creatures can attack in a band as long as at least one has "bands with other legen Forge: `Continuous`; XMage: `BandsWithOtherAbility, FilterCreaturePermanent, GainAbilityControlledEffect, SimpleStaticAbility`. Raw Forge: `S:Mode$ Continuous | Affected$ Creature.Black+Legendary+YouCtrl | AddKeyword$ Bands with Other Legendary Creatures | Description$ Black legendary crea`. Raw XMage: `import mage.abilities.common.SimpleStaticAbility; import mage.abilities.effects.common.continuous.GainAbilityControlledEffect; import mage.abilities.k`.
- `Nalathni Dragon` — Oracle excerpt: Flying; banding (Any creatures with banding, and up to one without, can attack in a band. Bands are blocked as a group. If any creatures with banding you control are blocking or be Forge: `Pump`; XMage: `AtTheBeginOfNextEndStepDelayedTriggeredAbility, BandingAbility, BoostSourceEffect, DelayedTriggeredAbility, FlyingAbility, NalathniDragonEffect, OneShotEffect, SacrificeSourceEffect`. Raw Forge: `A:AB$ Pump | Cost$ R | Defined$ Self | NumAtt$ +1 | SubAbility$ DBPump | SpellDescription$ CARDNAME gets +1/+0 until end of turn. If this ability has `. Raw XMage: `import mage.abilities.Ability; import mage.abilities.ActivationInfo; import mage.abilities.DelayedTriggeredAbility; import mage.abilities.common.Simpl`.
- `Seafarer's Quay` — Oracle excerpt: Blue legendary creatures you control have "bands with other legendary creatures." (Any legendary creatures can attack in a band as long as at least one has "bands with other legend Forge: `Continuous`; XMage: `BandsWithOtherAbility, FilterCreaturePermanent, GainAbilityControlledEffect, SimpleStaticAbility`. Raw Forge: `S:Mode$ Continuous | Affected$ Creature.Blue+Legendary+YouCtrl | AddKeyword$ Bands with Other Legendary Creatures | Description$ Blue legendary creatu`. Raw XMage: `import mage.abilities.common.SimpleStaticAbility; import mage.abilities.effects.common.continuous.GainAbilityControlledEffect; import mage.abilities.k`.

### Unresolved examples

- `Static Orb` — unmapped evidence retained: `Continuous`.
- `Sensory Deprivation` — unmapped evidence retained: `Attach, Continuous, AttachEffect, BoostEnchantedEffect, EnchantAbility, SimpleStaticAbility, TargetCreaturePermanent, TargetPermanent`.
- `Walking Sponge` — unmapped evidence retained: `Pump, GenericChoice, Animate, ContinuousEffect, FirstStrikeAbility, FlyingAbility, LoseAbilityTargetEffect, OneShotEffect, SimpleActivatedAbility, TapSourceCost, TargetCreaturePerm`.
- `Ravnica at War` — unmapped evidence retained: `ChangeZoneAll, ExileAllEffect, FilterPermanent`.
- `Torrent of Fire` — unmapped evidence retained: `DealDamage`.
- `Wyluli Wolf` — unmapped evidence retained: `Pump, BoostTargetEffect, SimpleActivatedAbility, TapSourceCost, TargetCreaturePermanent`.
- `Pteramander` — unmapped evidence retained: ``.
- `Nantuko Elder` — unmapped evidence retained: `Mana, SimpleManaAbility, TapSourceCost`.
- `Wei Strike Force` — unmapped evidence retained: `HorsemanshipAbility`.
- `Marang River Prowler` — unmapped evidence retained: `CantBlockBy, Continuous, CantBeBlockedSourceEffect, CantBlockSourceEffect, FilterControlledPermanent, MarangRiverProwlerCastEffect, SimpleStaticAbility`.

### Ambiguous or problematic joins

- `Teach by Example` — `forge`: `ambiguous_normalized_name`.
- `Battlewing Mystic` — `forge`: `ambiguous_normalized_name`.
- `Maze's Mantle` — `forge`: `ambiguous_normalized_name`.
- `The Mouth of Sauron` — `forge`: `ambiguous_normalized_name`.
- `Grief` — `forge`: `ambiguous_normalized_name`.
- `Squirrel Sanctuary` — `forge`: `ambiguous_normalized_name`.
- `Rugged Highlands` — `forge`: `ambiguous_normalized_name`.
- `Nazgûl Battle-Mace` — `forge`: `ambiguous_normalized_name`.
- `Bloom Tender` — `forge`: `ambiguous_normalized_name`.
- `Ancient Brass Dragon` — `forge`: `ambiguous_normalized_name`.

Observed matching issues include exact-name ambiguity and a small set of records with no exact Scryfall join. The current reports preserve those records in `ambiguous_matches.jsonl` and the source-specific unmatched files. Text mismatch is common: see measured comparisons above. Differences can be stale Oracle wording, templating, or a genuinely problematic join; this pass keeps the join and flags the difference rather than repairing it. The experiment does not systematically validate encoding or Java completeness.

## Assessment

1. Forge and XMage can bootstrap an evidence census over 46.77% of this Oracle corpus; the output remains implementation evidence, not a semantic census without review.
2. Forge evidence coverage: 71.46%.
3. XMage evidence coverage: 49.45%.
4. Both: 46.77%.
5. Repeated actions/classes support a small reviewed mapping seed; the CSV frequency tables give the actual distribution.
6. Exact-name ambiguity affects 1,511 records; normalized Oracle-text mismatch occurs for Forge 12,380 and XMage 9,518 matched records. Multiface names, absent fields, text currency, and non-card training examples need review.
7. Deterministic extraction is sufficient to create auditable candidates; it cannot establish correctness by agreement alone.
8. Small Phase 2: version-bound, risk-stratified human samples by pattern; blind double review for high-risk patterns; Wilson lower confidence bounds for precision; report reviewer agreement (simple agreement plus Cohen's kappa and Gwet's AC1 when useful); retain reviewer disagreement separately from extractor errors; stale validation when source, extractor, or mapping versions change; then make CAP eligibility an explicit versioned policy decision with a rule ID and reason. This repository does not yet implement that review or policy layer.

Authority boundary: Oracle text is card-specific input; this experiment does not retrieve Comprehensive Rules or official rulings. Forge and XMage are corroborating implementation witnesses only. No LLM, embeddings, or external classification service is used.
