# Requirement Model Review

## Scope

Review of the current Requirement primitives using only pinned repository evidence and existing validation metadata. No rules authority was fetched or integrated.

## Current Requirement model

Reviewed 14 current Requirements and 29 source evidence paths (13 reviewed paths, 16 unreviewed paths).

## Review methodology

Representative occurrences are selected by stable SHA-256 ordering of evidence path ID plus occurrence identity, with basic type/layout diversity. Counts refer to active occurrence populations in the card projection. Historical precision remains scoped to extractor 0.2.0; 0.2.1 transfer is exact-identity metadata only. No precision is combined at Requirement level.

## Requirement-by-Requirement findings

| Requirement | Evidence paths | Validated | Unreviewed | Primary status | Parameter issue | Overlap/boundary | Rules review |
|---|---:|---:|---:|---|---|---|---|
| `counter` | 1 | 0 | 1 | RENAME_CANDIDATE | 2 dimensions | see boundary catalog | deferred where normative |

### `counter`

**Intent:** An operation that counters a target spell or ability, as represented by the current XMage mapping.

**Status:** `RENAME_CANDIDATE`. Review the named parameter contract before expanding mappings or declaring model stability.

**Observed paths:** `xmage:CounterTargetEffect->counter`

**Validation state:** validated paths: none; unreviewed paths: `xmage:CounterTargetEffect->counter`. Unreviewed means not validated, not inconsistent.

**Parameter findings:** `countered_object` (REQUIRED; source fields: ValidTgts, ValidCards, Defined); `eligibility` (OPTIONAL; source fields: ValidTgts, ValidCards)

**Representative evidence:**
- Familiar's Ruse (`3b6d773b-e2f7-4e74-9e77-f2e0d369a31e`), xmage `CounterTargetEffect`, record `xmage@6212eb37907c1ce751d8a3fea8b3322056dc0264:row:00005026`, occurrence `evidence-occurrence:15863cdde6a68b7630d6daeb84e0182ecd2ca5c066d08ae1f606a2d63f2e03c7`; parameters `null`.
- Cerulean Drake (`ecd6587c-3548-4bc1-89e4-9f7fbbc2d2ad`), xmage `CounterTargetEffect`, record `xmage@6212eb37907c1ce751d8a3fea8b3322056dc0264:row:00002456`, occurrence `evidence-occurrence:0e839063f42390e745e7759536f4b1e9d02ac76e2072d622ed565e258a8c0ca2`; parameters `null`.

| `counter_change` | 2 | 2 | 0 | PARAMETER_MODEL_NEEDS_REVIEW | 4 dimensions | see boundary catalog | deferred where normative |

### `counter_change`

**Intent:** An operation that places or changes counters on an existing object; mapped constructs currently expose counter placement.

**Status:** `PARAMETER_MODEL_NEEDS_REVIEW`. Review the named parameter contract before expanding mappings or declaring model stability.

**Observed paths:** `forge:PutCounter->counter_change`, `xmage:AddCountersSourceEffect->counter_change`

**Validation state:** validated paths: `forge:PutCounter->counter_change`, `xmage:AddCountersSourceEffect->counter_change`; unreviewed paths: none. Unreviewed means not validated, not inconsistent.

**Parameter findings:** `counter_type` (REQUIRED; source fields: CounterType); `amount` (REQUIRED; source fields: CounterNum); `recipient` (REQUIRED; source fields: ValidTgts, ValidCards, Defined); `operation_direction` (NOT_ESTABLISHED; source fields: PutCounter, AddCountersSourceEffect)

**Representative evidence:**
- Crazed Firecat (`ba7cc6be-e575-4592-ada7-bbad3ae2225b`), forge `PutCounter`, record `forge@cef86f363d7f7d5b3293248a75f550a7c3404066:row:00004555`, occurrence `evidence-occurrence:d12c0cd18799db2c8497fed338fbf828d0e73ab8137ebfb66b7b3bcaca094e3b`; parameters `{"CounterNum": ["X"], "CounterType": ["P1P1"], "DB": ["PutCounter"], "Defined": ["Self"]}`.
- Invigorating Surge (`5daac63a-1534-4194-8cb7-506508e364f4`), forge `PutCounter`, record `forge@cef86f363d7f7d5b3293248a75f550a7c3404066:row:00016745`, occurrence `evidence-occurrence:214309a6b05a2f788f899751a109a7bd5c868c7cdd925831d87f216f3d7c513f`; parameters `{"Cost": ["2 G"], "CounterType": ["P1P1"], "SP": ["PutCounter"], "SpellDescription": ["Put a +1/+1 counter on target creature you control, then double the number of +1/+1 counters on that creature."], "SubAbility": ["DBPump"], "TgtPrompt": `.

| `create_token` | 2 | 1 | 1 | PARAMETER_MODEL_NEEDS_REVIEW | 4 dimensions | see boundary catalog | deferred where normative |

### `create_token`

**Intent:** Creation of one or more token objects with source-defined characteristics.

**Status:** `PARAMETER_MODEL_NEEDS_REVIEW`. Review the named parameter contract before expanding mappings or declaring model stability.

**Observed paths:** `forge:Token->create_token`, `xmage:CreateTokenEffect->create_token`

**Validation state:** validated paths: `forge:Token->create_token`; unreviewed paths: `xmage:CreateTokenEffect->create_token`. Unreviewed means not validated, not inconsistent.

**Parameter findings:** `token_definition` (REQUIRED; source fields: TokenScript, TokenPower, TokenToughness, TokenColor, TokenTypes); `quantity` (OPTIONAL; source fields: TokenAmount); `owner_or_controller` (SOURCE_SPECIFIC; source fields: TokenOwner, Defined); `entry_modifiers` (SOURCE_SPECIFIC; source fields: TokenTapped, TokenScript)

**Representative evidence:**
- Murgish Cemetery (`13a4d0a2-211b-41a9-809f-30025326ac51`), forge `Token`, record `forge@cef86f363d7f7d5b3293248a75f550a7c3404066:row:00004840`, occurrence `evidence-occurrence:03c4692eab7c4e18249f0dbf42e411604593a5c78b8bdd331e6c6e63eb42f9c4`; parameters `{"DB": ["Token"], "TokenPower": ["X"], "TokenScript": ["b_x_x_zombie"], "TokenToughness": ["X"]}`.
- Baku Altar (`8443b8c2-d0ab-4fb1-ad35-7e5e4cb345b6`), forge `Token`, record `forge@cef86f363d7f7d5b3293248a75f550a7c3404066:row:00005561`, occurrence `evidence-occurrence:6dae14eccb1847ed3de760d9adc4ca9417e6aa3f6780fe72d5c0632dae5dbaac`; parameters `{"AB": ["Token"], "Cost": ["2 T SubCounter<1/KI>"], "SpellDescription": ["Create a 1/1 colorless Spirit creature token."], "TokenAmount": ["1"], "TokenOwner": ["You"], "TokenScript": ["c_1_1_spirit"]}`.

| `damage` | 4 | 2 | 2 | PARAMETER_MODEL_NEEDS_REVIEW | 4 dimensions | see boundary catalog | deferred where normative |

### `damage`

**Intent:** Dealing a specified amount of damage to selected recipients.

**Status:** `PARAMETER_MODEL_NEEDS_REVIEW`. Review the named parameter contract before expanding mappings or declaring model stability.

**Observed paths:** `forge:DamageAll->damage`, `forge:DealDamage->damage`, `xmage:DamageAllEffect->damage`, `xmage:DamageTargetEffect->damage`

**Validation state:** validated paths: `forge:DealDamage->damage`, `xmage:DamageTargetEffect->damage`; unreviewed paths: `forge:DamageAll->damage`, `xmage:DamageAllEffect->damage`. Unreviewed means not validated, not inconsistent.

**Parameter findings:** `amount` (REQUIRED; source fields: NumDmg); `recipient_selection` (REQUIRED; source fields: ValidTgts, ValidCards, ValidPlayers, Defined); `cardinality_distribution` (SOURCE_SPECIFIC; source fields: TargetMin, TargetMax, DividedAsYouChoose); `damage_source` (OPTIONAL; source fields: DamageSource)

**Representative evidence:**
- Harbinger of the Hunt (`3256029f-6558-4fcc-9fa1-74ceba3e5c92`), forge `DamageAll`, record `forge@cef86f363d7f7d5b3293248a75f550a7c3404066:row:00004080`, occurrence `evidence-occurrence:34f9ca474b443e25a921cbbab9c129eca58c0a147eb6e1551ac10a450a1aeb9b`; parameters `{"AB": ["DamageAll"], "Cost": ["2 R"], "NumDmg": ["1"], "SpellDescription": ["CARDNAME deals 1 damage to each creature without flying."], "ValidCards": ["Creature.withoutFlying"], "ValidDescription": ["each creature without flying."]}`.
- Blockbuster (`11e50e35-bf4b-4089-b0c9-360d9c014584`), forge `DamageAll`, record `forge@cef86f363d7f7d5b3293248a75f550a7c3404066:row:00024613`, occurrence `evidence-occurrence:5b85fc1ae6c3828f83f939a01a3ac5308599203ce8de9118ec82ad9f230f85b5`; parameters `{"AB": ["DamageAll"], "Cost": ["1 R Sac<1/CARDNAME>"], "NumDmg": ["3"], "SpellDescription": ["CARDNAME deals 3 damage to each tapped creature and each player."], "ValidCards": ["Creature.tapped"], "ValidDescription": ["each tapped creature `.

| `destroy` | 4 | 2 | 2 | PARAMETER_MODEL_NEEDS_REVIEW | 3 dimensions | see boundary catalog | deferred where normative |

### `destroy`

**Intent:** Destroying selected objects that satisfy a source-defined selection.

**Status:** `PARAMETER_MODEL_NEEDS_REVIEW`. Review the named parameter contract before expanding mappings or declaring model stability.

**Observed paths:** `forge:Destroy->destroy`, `forge:DestroyAll->destroy`, `xmage:DestroyAllEffect->destroy`, `xmage:DestroyTargetEffect->destroy`

**Validation state:** validated paths: `forge:Destroy->destroy`, `xmage:DestroyTargetEffect->destroy`; unreviewed paths: `forge:DestroyAll->destroy`, `xmage:DestroyAllEffect->destroy`. Unreviewed means not validated, not inconsistent.

**Parameter findings:** `object_selection` (REQUIRED; source fields: ValidTgts, ValidCards, Defined); `cardinality` (REQUIRED; source fields: TargetMin, TargetMax, ValidCards); `modifiers` (SOURCE_SPECIFIC; source fields: NoRegen, RememberLKI, RememberDestroyed)

**Representative evidence:**
- Smash to Dust (`c13955b8-bad3-4f79-ad9f-11e214a1cab2`), forge `Destroy`, record `forge@cef86f363d7f7d5b3293248a75f550a7c3404066:row:00026696`, occurrence `evidence-occurrence:913bd5b7cc845806d941c0ba6696c572fb85c86a4cbb2ac1939d66f94ddc9e5b`; parameters `{"DB": ["Destroy"], "SpellDescription": ["Destroy target creature with defender."], "TgtPrompt": ["Select target creature with defender."], "ValidTgts": ["Creature.withDefender"]}`.
- Cruel Deceiver (`e0256da6-21f3-4019-9da0-75962b7f295c`), forge `Destroy`, record `forge@cef86f363d7f7d5b3293248a75f550a7c3404066:row:00015428`, occurrence `evidence-occurrence:8501448e47aeb95021efb69615ccab3af9cb8cee2bc70333e1393f0a0e4a356b`; parameters `{"DB": ["Destroy"], "Defined": ["TriggeredTargetLKICopy"]}`.

| `discard` | 1 | 0 | 1 | PARAMETER_MODEL_NEEDS_REVIEW | 4 dimensions | see boundary catalog | deferred where normative |

### `discard`

**Intent:** A player discarding selected cards from hand.

**Status:** `PARAMETER_MODEL_NEEDS_REVIEW`. Review the named parameter contract before expanding mappings or declaring model stability.

**Observed paths:** `forge:Discard->discard`

**Validation state:** validated paths: none; unreviewed paths: `forge:Discard->discard`. Unreviewed means not validated, not inconsistent.

**Parameter findings:** `discarding_player` (REQUIRED; source fields: ValidTgts, ValidPlayers, Defined); `card_selection` (REQUIRED; source fields: DiscardValid, Mode, Defined); `quantity` (REQUIRED; source fields: NumCards, Mode); `choice_and_reveal` (SOURCE_SPECIFIC; source fields: Mode, RevealDiscardAll)

**Representative evidence:**
- Thought Gorger (`ec5dc165-c760-4060-99fb-ec50f87374cb`), forge `Discard`, record `forge@cef86f363d7f7d5b3293248a75f550a7c3404066:row:00008762`, occurrence `evidence-occurrence:4fc2a9e42e1c5c3373242bb80055cb0ed5b837d4485e8e996b9de649a975a808`; parameters `{"ConditionDefined": ["Remembered"], "ConditionDescription": ["If you do,"], "ConditionPresent": ["Card"], "DB": ["Discard"], "Defined": ["You"], "Mode": ["Hand"], "SubAbility": ["DBCleanup"]}`.
- Shreds of Sanity (`6eaa343d-0097-4f05-80ab-deb016d4e15e`), forge `Discard`, record `forge@cef86f363d7f7d5b3293248a75f550a7c3404066:row:00019423`, occurrence `evidence-occurrence:9e82e7e40ce353c014759ad9ae7f8337270e8f67cf167c002e64d7c34ec48664`; parameters `{"DB": ["Discard"], "Defined": ["You"], "Mode": ["TgtChoose"], "NumCards": ["1"], "SubAbility": ["DBExile"]}`.

| `draw` | 2 | 1 | 1 | PARAMETER_MODEL_NEEDS_REVIEW | 3 dimensions | see boundary catalog | deferred where normative |

### `draw`

**Intent:** A player drawing one or more cards.

**Status:** `PARAMETER_MODEL_NEEDS_REVIEW`. Review the named parameter contract before expanding mappings or declaring model stability.

**Observed paths:** `forge:Draw->draw`, `xmage:DrawCardSourceControllerEffect->draw`

**Validation state:** validated paths: `forge:Draw->draw`; unreviewed paths: `xmage:DrawCardSourceControllerEffect->draw`. Unreviewed means not validated, not inconsistent.

**Parameter findings:** `drawing_player` (REQUIRED; source fields: Defined, ValidTgts, ValidPlayers); `quantity` (REQUIRED; source fields: NumCards); `conditionality` (SOURCE_SPECIFIC; source fields: ConditionPresent, OptionalDecider)

**Representative evidence:**
- Thought Gorger (`ec5dc165-c760-4060-99fb-ec50f87374cb`), forge `Draw`, record `forge@cef86f363d7f7d5b3293248a75f550a7c3404066:row:00008762`, occurrence `evidence-occurrence:23ef4d73ac6d8abd2ce48878070c0645139e57a99dbcb53a7ac882ce462b7aa0`; parameters `{"DB": ["Draw"], "Defined": ["TriggeredCardController"], "NumCards": ["Disgorge"]}`.
- Lost Isle Calling (`0efbf29c-09a0-4472-83ad-8d692c0232a5`), forge `Draw`, record `forge@cef86f363d7f7d5b3293248a75f550a7c3404066:row:00007157`, occurrence `evidence-occurrence:8552e1fa70ff916e2ad92fe13bd8a9f3d07644687083b36d92454cc736e1bb22`; parameters `{"AB": ["Draw"], "Cost": ["4 U U Exile<1/CARDNAME>"], "NumCards": ["X"], "SorcerySpeed": ["True"], "SpellDescription": ["Draw a card for each verse counter on CARDNAME. If it had seven or more verse counters on it, take an extra turn after `.

| `gain_life` | 2 | 1 | 1 | PARAMETER_MODEL_NEEDS_REVIEW | 2 dimensions | see boundary catalog | deferred where normative |

### `gain_life`

**Intent:** Increasing a player's life total by a source-defined amount.

**Status:** `PARAMETER_MODEL_NEEDS_REVIEW`. Review the named parameter contract before expanding mappings or declaring model stability.

**Observed paths:** `forge:GainLife->gain_life`, `xmage:GainLifeEffect->gain_life`

**Validation state:** validated paths: `xmage:GainLifeEffect->gain_life`; unreviewed paths: `forge:GainLife->gain_life`. Unreviewed means not validated, not inconsistent.

**Parameter findings:** `life_recipient` (REQUIRED; source fields: Defined, ValidTgts, ValidPlayers); `amount` (REQUIRED; source fields: LifeAmount)

**Representative evidence:**
- Grisly Sigil (`b9d9d118-a073-4e73-90fe-026462d1d895`), forge `GainLife`, record `forge@cef86f363d7f7d5b3293248a75f550a7c3404066:row:00015475`, occurrence `evidence-occurrence:91e7242722b04dbe96ad1bf641b0de8ac6628674fb9b1a67b494f3c4da6c56da`; parameters `{"DB": ["GainLife"], "LifeAmount": ["1"]}`.
- Bloodrite Invoker (`2dd3a6f7-65a9-4157-9ad9-13a885ebe927`), forge `GainLife`, record `forge@cef86f363d7f7d5b3293248a75f550a7c3404066:row:00001030`, occurrence `evidence-occurrence:aba8ece7d4e83640b8d1210f720452239e728bdc23f81aecf60f4cebc7efb09f`; parameters `{"DB": ["GainLife"], "Defined": ["You"], "LifeAmount": ["3"]}`.

| `lose_life` | 2 | 0 | 2 | PARAMETER_MODEL_NEEDS_REVIEW | 2 dimensions | see boundary catalog | deferred where normative |

### `lose_life`

**Intent:** Decreasing a player's life total by a source-defined amount.

**Status:** `PARAMETER_MODEL_NEEDS_REVIEW`. Review the named parameter contract before expanding mappings or declaring model stability.

**Observed paths:** `forge:LoseLife->lose_life`, `xmage:LoseLifeTargetEffect->lose_life`

**Validation state:** validated paths: none; unreviewed paths: `forge:LoseLife->lose_life`, `xmage:LoseLifeTargetEffect->lose_life`. Unreviewed means not validated, not inconsistent.

**Parameter findings:** `life_recipient` (REQUIRED; source fields: Defined, ValidTgts, ValidPlayers); `amount` (REQUIRED; source fields: LifeAmount)

**Representative evidence:**
- Alms of the Vein (`2013a774-e6ab-4f2d-a84f-fd277a637d7e`), forge `LoseLife`, record `forge@cef86f363d7f7d5b3293248a75f550a7c3404066:row:00025389`, occurrence `evidence-occurrence:3dc585b568a9e65c88d9deb99a200935e753148e17e114e5d14cf883f0a10f0e`; parameters `{"Cost": ["2 B"], "LifeAmount": ["3"], "SP": ["LoseLife"], "SpellDescription": ["Target opponent loses 3 life and you gain 3 life."], "SubAbility": ["DBGainLife"], "ValidTgts": ["Opponent"]}`.
- Diregraf Scavenger (`54731e3f-a84a-4fc9-8c02-2f769133c71c`), forge `LoseLife`, record `forge@cef86f363d7f7d5b3293248a75f550a7c3404066:row:00019182`, occurrence `evidence-occurrence:e540d11e4010d88a9c0bf5e51d209ba9034b22a57dbe2ba464d9ead1601386b2`; parameters `{"ConditionDefined": ["Remembered"], "ConditionPresent": ["Creature"], "DB": ["LoseLife"], "Defined": ["Player.Opponent"], "LifeAmount": ["2"], "SubAbility": ["DBGainLife"]}`.

| `mana_production` | 1 | 0 | 1 | PARAMETER_MODEL_NEEDS_REVIEW | 3 dimensions | see boundary catalog | deferred where normative |

### `mana_production`

**Intent:** Producing or adding mana with a source-defined kind, quantity, and restrictions.

**Status:** `PARAMETER_MODEL_NEEDS_REVIEW`. Review the named parameter contract before expanding mappings or declaring model stability.

**Observed paths:** `forge:Mana->mana_production`

**Validation state:** validated paths: none; unreviewed paths: `forge:Mana->mana_production`. Unreviewed means not validated, not inconsistent.

**Parameter findings:** `mana_kind_or_choice` (REQUIRED; source fields: Produced); `quantity` (REQUIRED; source fields: Amount, Produced); `restriction_and_duration` (SOURCE_SPECIFIC; source fields: RestrictValid, PersistentMana, TriggersWhenSpent)

**Representative evidence:**
- Bog Initiate (`23f93411-f83c-4ed2-abed-99cf905f7d7f`), forge `Mana`, record `forge@cef86f363d7f7d5b3293248a75f550a7c3404066:row:00027049`, occurrence `evidence-occurrence:c20f2c240287c6b85c833a8ec87184f255e4c3e72af62fb8bf90be26762449d5`; parameters `{"AB": ["Mana"], "Cost": ["1"], "Produced": ["B"], "SpellDescription": ["Add {B}."]}`.
- Drifting Meadow (`c6eb2814-0021-4308-ad44-6c8cc59b0d1c`), forge `Mana`, record `forge@cef86f363d7f7d5b3293248a75f550a7c3404066:row:00025881`, occurrence `evidence-occurrence:cef704eeecd77740c90420ed4cdf18c9aef5cc01d0bd8b32b4cae827c8ed3541`; parameters `{"AB": ["Mana"], "Cost": ["T"], "Produced": ["W"], "SpellDescription": ["Add {W}."]}`.

| `shuffle` | 1 | 0 | 1 | KEEP_AS_IS | 2 dimensions | see boundary catalog | deferred where normative |

### `shuffle`

**Intent:** Randomizing the order of a library or other source-defined card set.

**Status:** `KEEP_AS_IS`. Review the named parameter contract before expanding mappings or declaring model stability.

**Observed paths:** `forge:Shuffle->shuffle`

**Validation state:** validated paths: none; unreviewed paths: `forge:Shuffle->shuffle`. Unreviewed means not validated, not inconsistent.

**Parameter findings:** `shuffled_library_or_set` (REQUIRED; source fields: Defined, ValidTgts, ValidCards); `timing_or_choice` (SOURCE_SPECIFIC; source fields: Mode, Optional, SubAbility)

**Representative evidence:**
- Dichotomancy (`6d23f074-d84c-429b-9322-adc731f54a5b`), forge `Shuffle`, record `forge@cef86f363d7f7d5b3293248a75f550a7c3404066:row:00027230`, occurrence `evidence-occurrence:54f74ec7d5940f67bae8f8151c407006de7e10651fbd5d89f336fd51bfe3c8d0`; parameters `{"DB": ["Shuffle"], "Defined": ["ParentTarget"], "StackDescription": ["None"]}`.
- Knowledge Exploitation (`61ad3299-474a-400f-a1c1-b86024aca3e8`), forge `Shuffle`, record `forge@cef86f363d7f7d5b3293248a75f550a7c3404066:row:00026347`, occurrence `evidence-occurrence:34972284ae7683981f0e31fb4f779ccad7f816a3b159d4c6c05f17e21c4bc18d`; parameters `{"DB": ["Shuffle"], "Defined": ["RememberedController"], "SubAbility": ["DBCleanup"]}`.

| `tap` | 1 | 0 | 1 | PARAMETER_MODEL_NEEDS_REVIEW | 3 dimensions | see boundary catalog | deferred where normative |

### `tap`

**Intent:** Changing selected objects to tapped state.

**Status:** `PARAMETER_MODEL_NEEDS_REVIEW`. Review the named parameter contract before expanding mappings or declaring model stability.

**Observed paths:** `forge:Tap->tap`

**Validation state:** validated paths: none; unreviewed paths: `forge:Tap->tap`. Unreviewed means not validated, not inconsistent.

**Parameter findings:** `object_selection` (REQUIRED; source fields: ValidTgts, ValidCards, Defined); `cardinality` (SOURCE_SPECIFIC; source fields: TargetMin, TargetMax, ChangeNum); `cost_or_effect` (SOURCE_SPECIFIC; source fields: Cost, DB, SP, AB)

**Representative evidence:**
- Urge to Feed (`c9f2f0ae-5869-43dc-a225-4dfe3d37c166`), forge `Tap`, record `forge@cef86f363d7f7d5b3293248a75f550a7c3404066:row:00026713`, occurrence `evidence-occurrence:9986ac0b168b5e18bedfe4c0074f166ed1d6947b5839b0da94e485d552c12119`; parameters `{"AnyNumber": ["True"], "CardChoices": ["Vampire.YouCtrl+untapped"], "ChoiceAmount": ["Count$Valid Vampire.YouCtrl+untapped"], "DB": ["Tap"], "RememberTapped": ["True"], "SubAbility": ["VampiricFeed"]}`.
- Protocol Knight (`ac935fad-2fa7-4afc-9db4-3cd30ec4aabd`), forge `Tap`, record `forge@cef86f363d7f7d5b3293248a75f550a7c3404066:row:00002968`, occurrence `evidence-occurrence:0dcf6fb7284a09c1745ad85c89d53b2872ad1509cec5b15eda738f752bb976b6`; parameters `{"DB": ["Tap"], "SubAbility": ["DBCounter"], "TgtPrompt": ["Select target creature an opponent controls"], "ValidTgts": ["Creature.OppCtrl"]}`.

| `untap` | 2 | 0 | 2 | PARAMETER_MODEL_NEEDS_REVIEW | 3 dimensions | see boundary catalog | deferred where normative |

### `untap`

**Intent:** Changing selected objects to untapped state.

**Status:** `PARAMETER_MODEL_NEEDS_REVIEW`. Review the named parameter contract before expanding mappings or declaring model stability.

**Observed paths:** `forge:Untap->untap`, `xmage:UntapLandsEffect->untap`

**Validation state:** validated paths: none; unreviewed paths: `forge:Untap->untap`, `xmage:UntapLandsEffect->untap`. Unreviewed means not validated, not inconsistent.

**Parameter findings:** `object_selection` (REQUIRED; source fields: ValidTgts, ValidCards, Defined); `cardinality` (SOURCE_SPECIFIC; source fields: ChangeNum, ValidCards, UntapLandsEffect); `timing_context` (SOURCE_SPECIFIC; source fields: DB, AB, ConditionPresent)

**Representative evidence:**
- Nacre Talisman (`f87aaed9-7f78-4f8b-8af5-44d4be1d6f30`), forge `Untap`, record `forge@cef86f363d7f7d5b3293248a75f550a7c3404066:row:00017381`, occurrence `evidence-occurrence:08871ed375bb38f7945ba38d5ff95f7a777662b06d4bc255f912fbb82cdeefce`; parameters `{"AB": ["Untap"], "Cost": ["3"], "TgtPrompt": ["Select target permanent"], "ValidTgts": ["Permanent"]}`.
- Dream's Grip (`8b239262-c392-4ec6-9ae1-8b4a076e4bf0`), forge `Untap`, record `forge@cef86f363d7f7d5b3293248a75f550a7c3404066:row:00013472`, occurrence `evidence-occurrence:58a1b5c2c5edc9a90668a0f714ee89d443e1fde12cd0a275202dccf5e02be4f3`; parameters `{"DB": ["Untap"], "SpellDescription": ["Untap target permanent."], "TgtPrompt": ["Select target permanent to untap"], "ValidTgts": ["Permanent"]}`.

| `zone_transition` | 4 | 4 | 0 | PARAMETER_MODEL_NEEDS_REVIEW | 7 dimensions | see boundary catalog | deferred where normative |

### `zone_transition`

**Intent:** Moving an existing object from one zone to a different zone.

**Status:** `PARAMETER_MODEL_NEEDS_REVIEW`. Review the named parameter contract before expanding mappings or declaring model stability.

**Observed paths:** `forge:ChangeZone->zone_transition`, `forge:ChangeZoneAll->zone_transition`, `xmage:ExileTargetEffect->zone_transition`, `xmage:ReturnToHandSourceEffect->zone_transition`

**Validation state:** validated paths: `forge:ChangeZone->zone_transition`, `forge:ChangeZoneAll->zone_transition`, `xmage:ExileTargetEffect->zone_transition`, `xmage:ReturnToHandSourceEffect->zone_transition`; unreviewed paths: none. Unreviewed means not validated, not inconsistent.

**Parameter findings:** `origin` (REQUIRED; source fields: Origin); `destination` (REQUIRED; source fields: Destination); `object_selection` (REQUIRED; source fields: ValidTgts, ValidCards, ChangeType, Defined); `cardinality` (REQUIRED; source fields: ChangeNum, TargetMin, TargetMax); `owner_controller_visibility` (SOURCE_SPECIFIC; source fields: DefinedPlayer, Chooser, Hidden, Reveal, RememberChanged); `position_order` (SOURCE_SPECIFIC; source fields: LibraryPosition, RandomOrder); `timing_context` (SOURCE_SPECIFIC; source fields: Mode, TriggerZones)

**Representative evidence:**
- Vraska's Scorn (`020c26ba-ed46-47c3-925c-b9f32500f503`), forge `ChangeZone`, record `forge@cef86f363d7f7d5b3293248a75f550a7c3404066:row:00023712`, occurrence `evidence-occurrence:69b4df40c85128bf845dbf88595f86b5a49ffb92ab5f1278f8038074a3775ef4`; parameters `{"ChangeType": ["Card.YouOwn+namedVraska; Scheming Gorgon"], "DB": ["ChangeZone"], "Destination": ["Hand"], "Optional": ["True"], "Origin": ["Library"], "OriginAlternative": ["Graveyard"], "SpellDescription": ["You may search your library a`.
- Leonin of the Lost Pride (`3c692dd9-3986-46de-ac10-cc917b7c41b7`), forge `ChangeZone`, record `forge@cef86f363d7f7d5b3293248a75f550a7c3404066:row:00002451`, occurrence `evidence-occurrence:a96425b45bb4ab87389b0d53ee7b7fe488706801a3f46cb4f1c2cf79c8145bff`; parameters `{"DB": ["ChangeZone"], "Destination": ["Exile"], "Origin": ["Graveyard"], "TgtPrompt": ["Choose target card in an opponent's graveyard"], "ValidTgts": ["Card.OppOwn"]}`.

## Parameter-model findings

The projection preserves source-local parameters, but a Requirement ID alone cannot reconstruct amounts, selectors, cardinality, object recipient, counter/token definition, mana restrictions, or zone endpoints. The parameter contract records observed dimensions; it does not assert Comprehensive Rules requirements.

## Semantic boundary findings

- `counter` denotes countering a spell or ability in the current mapped examples; `counter_change` denotes placing counters. Keep separate; `counter` is a rename candidate because its bare name is easy to confuse with counter placement.
- `zone_transition` denotes movement between distinct zones. Same-zone library repositioning is historical excluded evidence under 0.2.1, not active evidence.
- `draw` and `discard` are distinct mapped actions even when a card also has Library/Hand/Graveyard movement evidence.
- `shuffle` is a distinct action and not a generic Library-to-Library transition.
- `damage` and `destroy` each group single-target and all-style constructs; current evidence suggests selection/cardinality parameters can retain that distinction.
- `tap`/`untap` and `gain_life`/`lose_life` are directional operations. A signed/shared abstraction has no concrete demonstrated benefit.

## Requirement overlap findings

Co-occurrence is not semantic equivalence. The boundary catalog contains deterministic source-backed Oracle-ID examples for counter/counter_change, draw/zone_transition, discard/zone_transition, shuffle/zone_transition, life direction, and tap direction. No merge or split is recommended from these overlaps alone.

## Potential model gaps

The deterministic unmapped-evidence scan found 5 candidate vocabulary gaps. They remain unassigned and do not imply full-corpus ontology coverage:

- `forge:ChangesZone` (5144 occurrences): Observed zone-change event/trigger vocabulary, distinct from an action that performs a zone transition. Example `Greta, Sweettooth Scourge` (`00173df7-a584-410c-af1d-ada9c791056a`), source record `forge@cef86f363d7f7d5b3293248a75f550a7c3404066:row:00009610`.
- `forge:DamageDone` (650 occurrences): Observed damage-event vocabulary; relation to damage action evidence needs explicit modeling review. Example `Vedalken Heretic` (`001c6369-df13-427d-89df-718d5c09f382`), source record `forge@cef86f363d7f7d5b3293248a75f550a7c3404066:row:00011849`.
- `forge:Pump` (3979 occurrences): Observed power/toughness modification vocabulary not represented by the current Requirement set. Example `Walking Sponge` (`000e5d65-96c3-498b-bd01-72b1a1991850`), source record `forge@cef86f363d7f7d5b3293248a75f550a7c3404066:row:00026253`.
- `xmage:BoostSourceEffect` (791 occurrences): Observed source power/toughness modification implementation class. Example `Whispering Shade` (`0036d062-10dc-4267-98b4-1d2f6b190a61`), source record `xmage@6212eb37907c1ce751d8a3fea8b3322056dc0264:row:00018220`.
- `xmage:BoostTargetEffect` (808 occurrences): Observed target power/toughness modification implementation class. Example `Wyluli Wolf` (`00185f3b-2777-4417-a8e0-4691f41c0ec1`), source record `xmage@6212eb37907c1ce751d8a3fea8b3322056dc0264:row:00018701`.

## Special audits

- **counter vs counter_change:** counter means countering a spell/ability in current examples; counter_change covers placing counters. Keep distinct; `counter` is a rename candidate due to ambiguity.
- **zone_transition:** coherent for distinct zone endpoints, with parameter-model review needed for selection, cardinality, visibility/ownership, position, and timing. Four adjudicated same-zone failures remain historical inactive evidence.
- **damage:** target and all-style paths appear parameterizable by recipient set, amount, cardinality, and distribution.
- **destroy:** target and all-style paths appear parameterizable by selection/cardinality/modifiers. The old import-only issue was extraction-level and is not reopened.
- **draw vs zone_transition:** preserve distinct mapped operations; co-occurrence does not merge them.
- **discard vs zone_transition:** preserve explicit discard as distinct from generic zone movement.
- **shuffle vs same-zone:** Shuffle is a distinct operation; equal-endpoint zone actions do not enter active zone_transition evidence under 0.2.1.
- **gain/lose life and tap/untap:** keep directional operations separate; no concrete benefit from a signed/shared abstraction is shown.


## Unreviewed evidence-path implications

Sixteen source paths remain unreviewed. Their observed constructs inform boundary and parameter inspection, but they are not marked validated or inconsistent and no statistical review packet was produced.

## Normative rules questions deferred

Exact Magic rules semantics, replacement/prevention interactions, layers, timing, and edge conditions need normative rules review where a later use requires those claims. This report makes no rules-correctness determination.

## Compatibility impact

No IDs, mappings, extractor behavior, projection, validation results, or samples changed. Future parameter normalization may affect projection schema and downstream persisted artifacts; renaming `counter` affects its mapping path, 145 card-Requirement pairs, review-pattern identity and future persisted IDs. Historical review remains tied to its prior scope.

## Recommended next phase

**PHASE_0_3_1_REQUIREMENT_MODEL_CORRECTIONS** — review parameter contracts and decide whether to version the `counter` name before expanding validation. The current evidence identifies material parameter-representation gaps; no correction is made here.

## Summary classifications

{"KEEP_AS_IS": 1, "PARAMETER_MODEL_NEEDS_REVIEW": 12, "RENAME_CANDIDATE": 1}

**MODEL_CORRECTIONS_REQUIRED = true**. This is a review recommendation, not an applied model change.
