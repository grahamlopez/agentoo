---
name: wallpaper-variants
description: Adapt wallpaper masters to multiple aspect ratios, extend scenes without cropping, upsample to exact resolutions, and build review galleries with revision history and portable JPEG exports. Use for wallpaper collections and follow-up image revisions.
---

# Wallpaper variants

Turn each master into a complete set of display-sized wallpapers, preserving the
original's spirit, subjects, and composition. Extend the scene to fit each shape;
never crop to fill. Keep the original files untouched and retain lossless PNG
working masters. For Agentoo's portable delivery collection, export JPEG quality
95 with 4:4:4 color sampling after reviewing the compositions, unless the user
requests lossless-only delivery or another format.

## Inputs and destination

Use the user's source folder and requested sizes. For Agentoo, the default sizes
are the eight native resolutions in [the wallpaper README](../README.md). The
helper reads that table when initializing a job, then snapshots the sizes in the
job manifest. Desktop scaling does not change the export size. A 2880 × 1920
Framework image also covers the smaller 3:2 panel by downsampling.

Use a new workspace output folder, normally `output/wallpapers/<job-name>/`.
Do not overwrite an earlier job or replace deployed wallpapers as part of an
export. Keep the JPEG delivery collection separate from PNGs and intermediates.

The deterministic helper is [scripts/wallpapers.py](scripts/wallpapers.py).
It needs Python with Pillow for inspection and FFmpeg for resampling. It does
not call a generation service. Run `--help` for its commands. In examples below,
`HELPER` means the actual path to this skill's `scripts/wallpapers.py`.

```sh
python HELPER init --source ~/Downloads/wallpapers --output output/wallpapers/my-job
# Optional replacement for the README defaults:
python HELPER init --source /path/to/masters --output output/wallpapers/custom --sizes 6144x2560 2880x1920
```

Initialization copies the originals, inventories their dimensions, creates the
manifest and gallery, and assigns stable master IDs. Resume an existing job
from its manifest rather than initializing it again.

## Inspect and generate

1. Inspect every original visually, not just its filename. Identify the subjects,
   their relative positions, props, lettering/logos, perspective, lighting,
   texture, palette, and elements that distinguish similar masters.
2. Read and follow the available `imagegen` skill when using image generation.
   Prefer the built-in image editing tool; inspect local edit targets with
   `view_image` before supplying their paths. Do not substitute an API/CLI
   generation workflow without the authorization that workflow requires.
3. Make one variant per master and target. Start with a representative wide and
   narrow shape to assess the approach before scaling up the batch. Reuse an
   approved composition at another resolution of the same aspect ratio when
   appropriate; the two 16:10 targets need not be independently regenerated.
4. Use the original as the edit target, not merely inspiration. Preserve all
   original content and its proportions. Fit the entire original within the
   target shape, then outpaint beyond its edges. Wide targets usually need
   lateral scenery; portrait targets often need substantial scene extension
   above and below. Do not solve portrait layouts by removing side characters,
   squeezing the image, or stacking/rearranging subjects.
5. Add only plausible continuations of the existing environment. Match geometry,
   perspective, atmosphere, materials and lighting. Avoid invented main subjects,
   duplicate characters, repeated scene panels, mirrored padding, borders and
   letterboxing. Preserve exact meaningful text and logos. Complete a subject
   already cut by the source edge only when consistent with the original.

Prompt scaffold (replace the bracketed portions with visual observations):

```text
Edit target: [original filename]. Create a faithful wallpaper variant at
[width] × [height], aspect [ratio]. Preserve [specific invariants], including
the full original composition and all four edges. Fit the entire original
proportionally in the new canvas and seamlessly extend [appropriate scenery]
[at the sides / above and below]. Keep [lighting, palette, perspective, style].
Never crop to fill, stretch, rearrange, omit, or duplicate original subjects.
Add no new main subjects, slogans, borders or repeated image panels.
Single continuous scene. Highest available resolution, lossless PNG output.
```

Ask for the target size but inspect the actual generated dimensions. The tool
may return a much smaller image despite the prompt. Do not describe an enlarged
1.6 MP generation as native-detail 4K or 6K. Generative reconstruction may also
change fine details; visually verify fidelity rather than promising pixel-level
preservation. Use higher-resolution generation or a suitable super-resolution
tool when available and authorized; disclose ordinary interpolation otherwise.

## Register, resize and review

Save the exact generation prompt to a text file. After inspecting the generated
composition, register it using the master ID printed by initialization:

```sh
python HELPER add --job output/wallpapers/my-job --master agent-smith --target 6144x2560 --image /path/to/generated.png --prompt-file /path/to/prompt.txt --note 'Extended the office at both sides.'
```

`add` copies the generated source into the job, creates a new version, resizes
with Lanczos, verifies exact dimensions and PNG integrity, and rebuilds the
gallery. It accepts only near-matching aspect ratios; a materially wrong shape
needs another outpaint, not stretching or cropping. Tiny pixel-rounding gaps
are filled from the boundary pixels. It keeps the actual generated dimensions
and processing method in the manifest. Lossless thumbnails keep the gallery
light without using the full export for every preview.

Inspect every returned composition and final export for subject preservation,
continuous extensions, meaningful lettering, visible seams and artifacts. Check
some native-size detail, especially faces, hands/feet, colored lines, and dark
gradients. Reject a crop-to-fill or subject-changing result and make a targeted
revision; do not repeatedly rerun an unchanged prompt. Keep unreviewed outputs
marked as such in the handoff rather than implying visual approval.

The gallery at `JOB/index.html` contains originals, target placeholders, version
previews, full-resolution links, and feedback fields. The user can preview older
versions and copy feedback identifying the master, target and revision. Browser
preview changes do not persist the chosen version; use `select` to do that.

For a revision, use the original plus the previous image when helpful, repeat the
invariants, and change only the requested feature. Run `add` again for that
master/target. Previous images and prompts remain available. To restore a version:

```sh
python HELPER select --job output/wallpapers/my-job --master agent-smith --target 6144x2560 --revision 1
python HELPER build --job output/wallpapers/my-job
```

`build` verifies all registered exports, reports missing targets, totals only
the selected final wallpapers, and regenerates the gallery without new image
generation. Complete the requested matrix before handing off unless a concrete
blocker or user steering prevents it. Report the gallery and manifest paths,
completed/expected count, selected-final size excluding intermediates/history,
generation method, and any resolution/fidelity limitations. Do not claim the
job is visually approved simply because its dimensions pass.

## Portable JPEG delivery

The established preset is standard JPEG, quality **95**, **4:4:4** color sampling
(`subsampling=0` in Pillow), optimized Huffman coding, and non-progressive output.
It balances compact files and broad decoder compatibility. JPEG remains lossy:
never call this preset lossless, artifact-free, or guaranteed visually identical.
In particular, colored lettering, neon lines and dark gradients need inspection.
Quality numbers are not interchangeable between codecs or encoders.

```sh
python HELPER export-jpeg --job output/wallpapers/my-job --output output/wallpapers/my-job-jpeg-q95
```

The command exports only the selected PNG revision for every master/target,
without changing dimensions or cropping. It requires a complete target matrix,
retains ICC profiles when present, and refuses existing nonempty destinations.
It checks full JPEG decoding, dimensions and 4:4:4 sampling, then writes a JPEG
gallery and manifest. Transparent images require an explicit compositing choice
before JPEG export; do not silently discard transparency.

Review actual JPEGs at native pixel size against their PNGs. The JPEG gallery's
previews are decoded from the JPEGs, and each card links to the PNG reference.
For an image edit, revise the lossless job and export a new JPEG collection into
a new destination; never repeatedly re-encode JPEGs. The manifest records source
revisions so gallery feedback can identify the right lossless variant.

Report JPEG count, total JPEG bytes/MiB, PNG baseline and percentage reduction.
Exclude thumbnails, generated sources, manifests and older revisions from these
totals. Link the JPEG gallery alongside the lossless review gallery. Do not treat
successful decoding as evidence of unchanged visual quality.

If the user wants a different compression tradeoff, benchmark a representative
subset first: faces, fine circuitry, neon edges and shadow gradients. Compare
full-resolution encodes; verify decoded-pixel equality for lossless candidates,
and inspect native-pixel crops for lossy candidates. Keep benchmarks isolated.
Do not promise savings based on the initial collection or generic codec averages.
