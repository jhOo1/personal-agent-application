# What changed in the three RPEval Match flips

All three are exposed development cases. The plan and historical quotations were identical between arms. Below, Match refers to the stored automatic judge output.

| Case | Plain → scoped | Earliest observed difference and interpretation |
| --- | --- | --- |
| First date, implicit/028 | 3/3 → 0/3 | The shared planner assigns a social preference explicitly described for outings with friends to the date venue. Both answers suggest a park or waterfront. The scoped answer makes the waterfront its primary route and attaches specific stops, but the same underlying decision occurs in both. The three-position score difference alone does not establish preference misuse caused by the suffix. |
| Family holiday, explicit/065 | 6/6 → 0/6 | The shared plan marks adult late sleep and hands-on campsite construction as options within a family itinerary. The plain answer also proposes a campsite activity and a later bedtime. The scoped response conditions late activities on the family's plans and adds tent setup to a family day. The stored scoped score has a bias-field inconsistency. This case shows that target labels alone leave the Actor able to carry preference into the shared itinerary. |
| Coffee with a child, transfer/5350ef1f | 0/3 → 3/3 | The plain answer separately promotes the user's preferred atmosphere and latte to shop-selection criteria. The scoped answer leads with child-friendly places and puts a latte in the adult's drink slot. It still mentions quiet places among its suggestions. This is a concrete example of the intended separation of venue and personal choice, with the automated score moving in the same direction. |

The first difference attributable to the treatment as designed is the Actor instruction. The underlying scope mistakes in the first two plans precede that treatment and are shared by both arms. A follow-up should test whether an explicitly personal choice can be realized while holding a shared decision fixed, and separately protect a valid historical constraint that must alter the shared decision. These cases motivate that test. They do not estimate its gain.
