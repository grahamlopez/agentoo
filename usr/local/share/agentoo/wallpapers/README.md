# Agentoo wallpapers

System-owned wallpaper collection. Add images here, grouped into ordinary
subdirectories as useful. Subdirectories have no special meaning.

Select an image with `agentoo desktop wallpaper set FILE`. Personal images can
live anywhere readable; the command remembers their absolute path without
copying them. Future themes may reference this collection.

For agents adapting a folder of originals to these display sizes, use the
[wallpaper-variants skill](wallpaper-variants/SKILL.md). It covers scene extension
without cropping, exact-size PNG masters, portable JPEG quality 95 / 4:4:4 exports,
and review galleries with revision history.

## Wallpaper target sizes

Use these eight native pixel sizes for wallpaper exports. Desktop scaling does
not change the target dimensions. Dell partitions can appear on either side
of the panel; the size depends on the partition's share of the full width.

| Display or partition | Dimensions (width × height) | Aspect ratio |
| --- | --- | --- |
| Dell U5226KW, full width | 6144 × 2560 | 12:5 |
| Dell U5226KW, 75% partition | 4608 × 2560 | 9:5 |
| Dell U5226KW, ⅔ partition | 4096 × 2560 | 16:10 |
| Dell U5226KW, 50% partition | 3072 × 2560 | 6:5 |
| Dell U5226KW, ⅓ partition | 2048 × 2560 | 4:5 |
| Dell U5226KW, 25% partition | 1536 × 2560 | 3:5 |
| Current laptop, 4K 16:10 display | 3840 × 2400 | 16:10 |
| Framework Laptop 13, 2.8K display | 2880 × 1920 | 3:2 |

The Dell's two-window PbP layouts pair 50/50, 25/75, 75/25, ⅓/⅔, or ⅔/⅓
partitions. The same sizes also cover three equal columns, 25/50/25, and four
equal columns.

The Framework export also covers the smaller 2256 × 1504 display: both panels
are 3:2, so downsampling preserves the composition without cropping or
distortion. The scale factor is fractional, so resampling is required.
