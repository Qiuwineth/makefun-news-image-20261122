[![make.fun · news-image-20261122](https://make.fun/badge/news-image-20261122.svg)](https://make.fun/bounty/news-image-20261122?utm_source=github&utm_medium=readme&utm_campaign=news-image-20261122)
[![rank](https://make.fun/badge/news-image-20261122/Qiuwineth/makefun-news-image-20261122/rank.svg)](https://make.fun/bounty/news-image-20261122/leaderboard?utm_source=github&utm_medium=readme&utm_campaign=news-image-20261122)
[![reward](https://make.fun/badge/news-image-20261122/Qiuwineth/makefun-news-image-20261122/reward.svg)](https://make.fun/bounty/news-image-20261122?utm_source=github&utm_medium=readme&utm_campaign=news-image-20261122)

# THE WORLD ON SUNDAY — 22 November 2026

One day, one picture: a dense newspaper front page summing up 22 November
2026's world news in a single 1024×1024 image.

The lead is the aftermath of the Trump–Xi–Putin trilateral summit in
Shenzhen and its "declaration of peace". Around it: the FBI's NCIC criminal
database hack, the Indonesian confectionery factory fire, the Nigerian
funeral boat disaster, Verstappen's Las Vegas Grand Prix win, the South
Korean education minister's resignation, and Nepal PM Balendra Shah's state
visit to India — plus markets and in-brief panels.

## Running

```
python3 poster.py
```

Pure Python standard library only — the renderer brings its own
rasterizer, stroke font and PNG encoder (no Pillow, no system fonts, no
network). It writes `entry.png` next to the script, or into
`$MAKEFUN_OUTPUT_DIR` when that variable is set. Output is deterministic:
same input, byte-identical PNG.
