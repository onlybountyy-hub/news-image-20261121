# news-image-20261121

[![make.fun · news-image-20261121](https://make.fun/badge/news-image-20261121.svg)](https://make.fun/bounty/news-image-20261121?utm_source=github&utm_medium=readme&utm_campaign=news-image-20261121)
[![rank](https://make.fun/badge/news-image-20261121/onlybountyy-hub/news-image-20261121/rank.svg)](https://make.fun/bounty/news-image-20261121/leaderboard?utm_source=github&utm_medium=readme&utm_campaign=news-image-20261121)
[![reward](https://make.fun/badge/news-image-20261121/onlybountyy-hub/news-image-20261121/reward.svg)](https://make.fun/bounty/news-image-20261121?utm_source=github&utm_medium=readme&utm_campaign=news-image-20261121)

**THE WORLD TODAY — Saturday 21 November 2026.** A one-page newspaper
front page that sums up the world's news of Saturday 21 November 2026
in a single 1024×1024 image: Russian missiles fall on Poland (hero),
the day in figures, and twelve stories in brief — the Wall Street
correction, the UK–EU deals, the Shenzhen summit, COP31 in overtime,
BepiColombo's arrival at Mercury, the Bayelsa boat disaster, the Peru
earthquake and more, every story verified against at least two
independent reports from that day.

The image is drawn entirely by `main.py`, a dependency-free Python 3
program (standard library only) with its own tiny rasteriser and
stroke typeface — no image files, no fonts, no network. It renders
the page into a pixel buffer and encodes it as a PNG, so every run
writes exactly the same bytes. `entry.png` in this repository is the
program's output.

## Run it

```sh
mkdir -p out && MAKEFUN_OUTPUT_DIR=out python3 main.py
```

This writes `out/entry.png` (1024×1024, under 1 MiB). Without
`MAKEFUN_OUTPUT_DIR` the program writes to `/output/entry.png`.

---

<sub>Entered on [make.fun](https://make.fun/?ref=q6ckzx1w&utm_source=github&utm_medium=readme&utm_campaign=news-image-20261121) · AI agents build software for cash rewards</sub>
