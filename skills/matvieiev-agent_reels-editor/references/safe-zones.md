# Safe zones: where text may live

Measured from a real iPhone profile grid, not from documentation. These numbers
are why a technically perfect Reel can still collect 96 impressions.

## The two crops

A Reel is seen in two places, and they crop differently.

**Profile grid.** The tile is 438×585 px — a 3:4 ratio. Your frame is 1080×1920
— a 9:16 ratio. The platform takes the **centre** and throws away the rest:

```
1080×1920 frame          what the grid shows
┌─────────────┐  y=0
│▓▓▓▓▓▓▓▓▓▓▓▓▓│         240 px — GONE
├─────────────┤  y=480
│             │
│   VISIBLE   │         1080×1440 survives
│             │
├─────────────┤  y=1350
│▓▓▓▓▓▓▓▓▓▓▓▓▓│         240 px — GONE
└─────────────┘  y=1920
```

**Full-screen player.** Nothing is cropped, but the top carries the player
header and the bottom-right carries the like / comment / share column, plus the
caption strip along the bottom.

The intersection of "survives the grid" and "not under platform UI" is the only
place text belongs.

## The zone

```
x: 50 … 1010     (50 px margin each side)
y: 480 … 1350
```

Anything above `y=480` does not exist as far as the grid is concerned.

**Captions** sit around 22% of frame height from the bottom — roughly
`y=1350…1500` in the player, clear of the button column.

**The hook** goes at 60–70% of frame height. Not the top. The top is where
instinct puts a title and where the platform deletes it.

## Type size

From posts that performed, on 1080×1920:

| Element | Cap height | Notes |
|---|---|---|
| Hook | 67 px | Readable at 438 px tile width |
| Captions | ~76 px font size | 3 words per screen maximum |

Test it honestly: scale your frame down to 438 px wide and look at it on a
phone. If you have to lean in, it is too small.

## Hook checklist

Before rendering, all five must be true:

- [ ] Sits inside `y 480…1350`
- [ ] Is a **claim**, not a label — something a viewer could disagree with
- [ ] Contains a number, a timeframe, or a price where one honestly applies
- [ ] Readable at 438 px width
- [ ] The frame behind it is a face or a scene — never a laptop screen; small
      text on a screen becomes grey noise at tile size

## Worked example

The Reel that produced these measurements:

| | Before | After |
|---|---|---|
| Hook position | top of frame | y=1150 |
| Grid result | first line cut, "монтує мої Reels" left dangling | fully readable |
| Wording | "Claude Code монтує мої Reels" | "Монтаж коштував $10. Агент робить за 3 хвилини" |
| Background | laptop screen | face |
| Impressions | **96** | — |
| Neighbours the same week | 1029, 1183 | — |

The edit, the captions and the audio were all correct. Only the hook was wrong,
and that was enough to lose an order of magnitude of reach.
