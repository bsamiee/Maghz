# [VISUALS]

Every visual output — interactive frame, thumbnail, chart, vector export, document page — is one row over one render capsule: a scene records once into an immutable `SKPicture` behind an op-budget gate, target kinds are rows over one frozen render-policy record, and what leaves the capsule is a value with its receipt, never a canvas or a live native. Text shapes before it rasters through one typography-role grid; vector, icon, and raster assets admit once into a frozen catalog whose failure modes are boot facts; a chart is a fold over a series-spec table whose evidence twin renders headless from the same values; and theme, typography, motion, locale, and iconography are five instantiations of one frozen token algebra — a total variant-by-density grid, one pure resolve fold, one atomic generation swap with a changed-key diff — so a literal paint, font, duration, or easing at a call site is the defect this page exists to delete. Growth lands as rows: a new target, role, asset class, series kind, or tokenized concern is one declaration inside an existing owner, never new pipeline code.

## [01]-[VISUALS_CHOOSER]

This table routes a visual concern to its owning surface; the most specific row wins.

| [INDEX] | [CONCERN]           | [OWNER]                               | [REJECTED_FORM]             |
| :-----: | :------------------ | :------------------------------------ | :-------------------------- |
|  [01]   | output target       | target row over one render capsule    | bespoke pipeline per target |
|  [02]   | retained scene      | one gated recorded `SKPicture`        | `SKBitmap` working surface  |
|  [03]   | frame identity      | pinned-projection hash receipt        | encoded-artifact hash       |
|  [04]   | document artifact   | page-protocol fold + dual receipt     | dispose-only export         |
|  [05]   | text on any surface | shaped run via the role grid          | paint-carried font state    |
|  [06]   | font fallback       | frozen role × script grid             | host registry probe at draw |
|  [07]   | vector asset        | admitted owner + variant matrix       | draw-time tint filter       |
|  [08]   | icon                | (`Symbol`, `IconVariant`) catalog row | string-keyed registry       |
|  [09]   | raster asset        | codec admission + two-key receipt     | eager whole-image decode    |
|  [10]   | chart               | series-spec table + headless twin     | per-chart code-behind       |
|  [11]   | styling values      | one frozen token algebra              | call-site literals          |
|  [12]   | color motion        | perceptual tween row                  | componentwise sRGB lerp     |

## [02]-[RENDER_LAW]

[SCENE_AND_TARGETS]:
- Law: a scene records once — `SKPictureRecorder.BeginRecording(cullRect, useRTree: true)` yields the immutable `SKPicture` every target replays, the R-tree making playback against a clip skip out-of-bounds ops — and `CullRect` is a contract, not a hint: content outside it may be elided, and layout reads it as the declared extent.
- Law: target kinds are rows over one frozen policy record — pinned `SKImageInfo`, `SKSurfaceProperties`, declared `SKSamplingOptions`, op and byte ceilings — so a new output target is one row and zero pipeline code; `BytesSize64` gates dimensions because the `int` size forms overflow past ~2 GB.
- Law: cost is computable before pixels — `ApproximateOperationCount` and `ApproximateBytesUsed` are the `SKPicture` recording receipts read after `EndRecording`, and `GetApproximateOperationCount(includeNested: true)` folds sub-pictures into the count — so a scene over the op ceiling fails a structural gate without ever allocating a surface, and the cost-probe target carries `Option` absence in the hash slot, never a sentinel string.
- Law: `SaveLayer` is earned only by group compositing — group alpha, blend, or image filter over a subtree — and always carries computed bounds, because the unbounded overload allocates clip-sized layers and per-shape alpha rides the paint; `QuickReject` culls expensive subtrees against device clip and total matrix before any draw.
- Reject: per-draw `new SKPaint()` — token-resolved long-lived and pooled-scratch `Reset()` are the two legal paint lifetimes; `UniqueId` as cache identity — it is process-local, never content identity; snapshot-then-keep-drawing — `Snapshot()` is copy-on-write, so the capsule orders snapshot last; and `Clear`-versus-`DrawColor` confusion — `Clear` replaces pixels including alpha while `DrawColor` composites, differing exactly on translucent fills over reused surfaces, the ghost-frame defect.
- Exemption: the capsule's using-scoped recorder, surface, and pixmap bodies are the platform-forced statement seam.

```csharp conceptual
[Union(ConversionFromValue = ConversionOperatorsGeneration.None)]
public abstract partial record Target {
    private Target() { }
    public sealed record Evidence : Target;
    public sealed record Thumbnail(float Scale) : Target;
    public sealed record CostProbe : Target;
}

public sealed record RenderPolicy(SKImageInfo Pinned, SKSurfaceProperties Props, int OpCeiling, long ByteCeiling);
public readonly record struct NativeFormat(SKColorType ColorType, SKAlphaType Alpha);
public readonly record struct FrameReceipt(Option<string> Hash, SKImageInfo Info, NativeFormat Native, int Ops);

public static class RenderCapsule {
    public static Fin<SKPicture> Record(RenderPolicy policy, SKRect cull, Action<SKCanvas> scene) {
        ArgumentNullException.ThrowIfNull(policy);
        ArgumentNullException.ThrowIfNull(scene);
        using var recorder = new SKPictureRecorder();
        scene(recorder.BeginRecording(cull, useRTree: true));
        return recorder.EndRecording() is var recorded && recorded.ApproximateOperationCount <= policy.OpCeiling
            ? Fin.Succ(recorded)
            : (fun(recorded.Dispose)(), Fin.Fail<SKPicture>(Error.New(7801, $"<op-budget:{recorded.ApproximateOperationCount}:{policy.OpCeiling}>"))).Item2;
    }

    public static Fin<FrameReceipt> Project(Target target, RenderPolicy policy, SKPicture scene) {
        ArgumentNullException.ThrowIfNull(target);
        return target.Switch(
            state: (Policy: policy, Scene: scene),
            evidence: static (s, _) => Raster(s.Policy.Pinned, s.Policy, s.Scene, 1f),
            thumbnail: static (s, t) => Raster(s.Policy.Pinned.WithSize(
                new SKSizeI((int)(s.Policy.Pinned.Width * t.Scale), (int)(s.Policy.Pinned.Height * t.Scale))), s.Policy, s.Scene, t.Scale),
            costProbe: static (s, _) => Fin.Succ(new FrameReceipt(None, s.Policy.Pinned,
                new NativeFormat(s.Policy.Pinned.ColorType, s.Policy.Pinned.AlphaType), s.Scene.GetApproximateOperationCount(includeNested: true))));
    }

    static Fin<FrameReceipt> Raster(SKImageInfo info, RenderPolicy policy, SKPicture scene, float scale) {
        if (info.BytesSize64 > policy.ByteCeiling) { return Fin.Fail<FrameReceipt>(Error.New(7802, $"<byte-gate:{info.BytesSize64}>")); }
        using var surface = SKSurface.Create(info, policy.Props);
        surface.Canvas.Clear(SKColors.Transparent);
        surface.Canvas.Scale(scale);
        surface.Canvas.DrawPicture(scene);
        using var pixels = surface.PeekPixels();
        return new FrameReceipt(
            Some(XxHash3.HashToUInt64(pixels.GetPixelSpan()).ToString("x16", CultureInfo.InvariantCulture)),
            info, new NativeFormat(info.ColorType, info.AlphaType), scene.ApproximateOperationCount);
    }
}
```

[PAINT_AND_COLOR]:
- Law: effect slots — `Shader`, `ColorFilter`, `ImageFilter`, `MaskFilter`, `PathEffect`, `BlendMode` — hold immutable reference-counted natives constructed once at token resolve and shared across paints; per-frame effect construction is the allocation defect, and stroke styling is path-effect data, never pre-deformed geometry.
- Law: every image draw declares `SKSamplingOptions(SKFilterMode, SKMipmapMode)` — the implicit default is nearest-neighbor and silently degrades scaled output — and `SetColor(SKColorF, SKColorSpace)` is the only color-managed paint entry: the byte `SKColor` path assumes sRGB and quantizes before any conversion, so wide gamut is float end-to-end or it is fiction.
- Law: color-space identity is `SKColorSpace.Equal`, never reference equality; a null color space means passthrough — fast and exactly wrong for evidence — and composite-heavy pipelines declare a linear working surface (`CreateSrgbLinear`) converting to sRGB once at the final projection, one boundary conversion instead of wrong blend math everywhere.
- Law: glyph state lives on `SKFont` — every text property on the paint is the obsolete rail — and custom raster math enters as `SKRuntimeEffect.CreateShader(sksl, out errors)` compiled once, the `errors` out-channel its rejection seam, never a per-pixel managed loop.

[EVIDENCE_IDENTITY]:
- Law: frame identity hashes the pinned pixel projection, never encoder output — encoded bytes couple identity to compression internals — and the evidence info declares all four fields, because `SKImageInfo.PlatformColorType` swaps byte order across hosts and premul is the native format pinned for a baseline's lifetime.
- Law: evidence renders on raster surfaces only — GPU output varies by driver, MSAA resolve, and backend, so the GPU path is throughput, never identity — and the receipt is composite: content hash, declared info, and the `(SKColorType, SKAlphaType)` native row the host resolved, so a hash divergence decomposes into a content change versus a `PlatformColorType` byte-order swap from the receipt alone instead of staying mysterious.
- Law: baselines are content-addressed by the receipt — two proofs rendering one scene under one policy share one baseline, and a policy edit re-keys every dependent baseline at once, so churn is proportional to policy change, not proof count; a stochastic effect carries its seed in its token row or it is a per-frame hash break by design.
- Law: deterministic encoding rides the knob-pinned `SKPixmap.Encode` rows (`SKPngEncoderOptions`), never the image convenience overloads; `SKImage.FromEncodedData` defers decode and retains `EncodedData` for pass-through re-export — correct for draw-once and forward-the-bytes lanes only, because lazy images re-decode under cache pressure with floating defaults.
- Boundary: the frame content hash is the in-process content-key choice the system-API identity owner fixes — `XxHash3.HashToUInt64` over the pinned pixel span, reused verbatim — never a second hashing path minted here; a persisted or signed artifact key is the durable byte-identity owner's canonical codec, composed at the export seam.

[DOCUMENT_EXPORT]:
- Law: a document is a forward-only page fold — `BeginPage` returns a canvas valid only until `EndPage`, `Close()` finalizes, `Abort()` discards — and the failure arm aborts explicitly: a capsule that merely disposes has neither committed nor failed loudly, the silent-loss defect; `SKDocument.CreateXps` shares the page protocol, so format is one row whose only divergence is the metadata argument's presence.
- Law: scene content enters pages as pictures so vectors and text survive — rasterizing vectors into a document is the fidelity defect — and `EncodingQuality` is a discontinuity, not a gradient: 101 is lossless, 100 and below switch embedded raster to JPEG, so the lossless row is mandatory for artifacts re-entering hash gates.
- Law: document bytes embed timestamps — byte identity requires pinned `Creation`/`Modified` — and the receipt is dual: per-page replay through the capsule's evidence target plus byte length, so a metadata-only change moves byte identity while page hashes hold, attributable without opening the file.
- Boundary: the durable commit composes the atomic-write law; this lane contributes the `Close()`-before-commit ordering edge and the receipt.

```csharp conceptual
[SmartEnum<string>]
public sealed partial class DocumentFormat {
    public static readonly DocumentFormat Pdf = new("<format-a>", static (sink, stamp) => SKDocument.CreatePdf(sink,
        new SKDocumentPdfMetadata { Creation = stamp, Modified = stamp, RasterDpi = 72f, EncodingQuality = 101 }));
    public static readonly DocumentFormat Xps = new("<format-b>", static (sink, _) => SKDocument.CreateXps(sink));

    [UseDelegateFromConstructor]
    public partial SKDocument Open(Stream sink, DateTime stamp);
}

public sealed record PageSpec(float Width, float Height, SKPicture Content);
public readonly record struct PageReceipt(int Index, Option<string> Hash, int Ops);
public sealed record ExportReceipt(Seq<PageReceipt> Pages, long ByteLength);

public static class DocumentExport {
    public static Fin<ExportReceipt> Commit(DocumentFormat format, Stream sink, Seq<PageSpec> pages, RenderPolicy evidence, DateTime stamp) {
        ArgumentNullException.ThrowIfNull(format);
        ArgumentNullException.ThrowIfNull(sink);
        using var document = format.Open(sink, stamp);
        return Try.lift<Fin<ExportReceipt>>(() => pages.Map((page, index) => Emit(document, evidence, index, page))
                .TraverseM(identity).As()
                .Map(receipts => (fun(document.Close)(), new ExportReceipt(receipts.Strict(), sink.Length)).Item2))
            .Run().Bind(static result => result)
            .MapFail(error => (fun(document.Abort)(), Error.New(7901, $"<export-aborted:{error.Message}>")).Item2);
    }

    static Fin<PageReceipt> Emit(SKDocument document, RenderPolicy evidence, int index, PageSpec page) {
        var canvas = document.BeginPage(page.Width, page.Height);
        canvas.DrawPicture(page.Content);
        document.EndPage();
        return RenderCapsule.Project(new Target.Evidence(), evidence, page.Content)
            .Map(receipt => new PageReceipt(index, receipt.Hash, receipt.Ops));
    }
}
```

## [03]-[TEXT_LAW]

[SHAPE_PIPELINE]:
- Law: text shapes before it rasters — `SKShaper` is the typeface-bound convenience, the raw `Buffer` + `Font` + `Feature` surface the control altitude, and escalation is a row swap: the moment OpenType features, script pinning, or cluster policy matter, the pipeline drops to `Font.Shape(buffer, features)` with range-scoped feature values.
- Law: the buffer protocol is ordered — add text, pin `Direction`, `Script`, and `Language`, shape, then read the zero-allocation `GetGlyphInfoSpan()`/`GetGlyphPositionSpan()` (the `GlyphInfos`/`GlyphPositions` array properties recopy per access) — and deterministic pipelines pin all axes as one run-spec row, because `GuessSegmentProperties` drifts at mixed-script margins and locales legitimately shape identical text to different glyph streams, which is why language joins the shaped-run cache key.
- Law: windowed shaping adds the item-window overloads with `Flags` edge contracts (`BeginningOfText`, `EndOfText`); pre-slicing the string severs cross-boundary joining forms — the run-segmentation defect.
- Law: positions project by `Size / 512f` with `YOffset` negated — shaping space is y-up, the canvas y-down — and the shaped run is the single measurement authority: advance-sum width reserves layout, ink bounds size invalidation, two queries never interchanged.
- Law: `ClusterLevel` is a typography-role decision riding the run-spec row, because hit-testing and selection cannot be retrofitted onto a stream shaped at the wrong level; wrapping folds over cluster boundaries with `GlyphFlags.UnsafeToBreak` bounding re-shape work to flagged break sites, and truncation picks the last fitting cluster boundary, never a char index.
- Law: one font file admits once and feeds both shaping and raster — `OpenStream(out ttcIndex)` into the zero-copy blob bridge, the `ttcIndex` load-bearing for collection files — and `SerializeGlyphs` is the shaping-evidence channel that catches shaping regressions without pixel comparison.
- Exemption: the span-backed run fill is the measured-kernel statement seam.

```csharp conceptual
public sealed class FontHandle : IDisposable {
    public const int DesignScale = 512;
    readonly Blob blob;
    readonly Face face;

    public FontHandle(SKTypeface typeface) {
        ArgumentNullException.ThrowIfNull(typeface);
        using var stream = typeface.OpenStream(out var ttcIndex);
        blob = stream.ToHarfBuzzBlob(); face = new Face(blob, ttcIndex); face.MakeImmutable();
        Font = new Font(face); Font.SetScale(DesignScale, DesignScale);
    }

    public Font Font { get; }

    public void Dispose() { Font.Dispose(); face.Dispose(); blob.Dispose(); }
}

public readonly record struct RunSpec(Direction Direction, Script Script, Language Language, ClusterLevel Level);
public sealed record ShapedRun(SKTextBlob Blob, float Width, ImmutableArray<int> Clusters);

public static class ShapeBoundary {
    public static ShapedRun Shape(string text, RunSpec spec, Font font, SKFont raster, params Feature[] features) {
        ArgumentNullException.ThrowIfNull(font);
        ArgumentNullException.ThrowIfNull(raster);
        using var buffer = new Buffer();
        buffer.AddUtf16(text);
        (buffer.Direction, buffer.Script, buffer.Language, buffer.ClusterLevel) = (spec.Direction, spec.Script, spec.Language, spec.Level);
        font.Shape(buffer, features);
        ReadOnlySpan<GlyphInfo> infos = buffer.GetGlyphInfoSpan();
        ReadOnlySpan<GlyphPosition> positions = buffer.GetGlyphPositionSpan();
        var scale = raster.Size / (float)FontHandle.DesignScale;
        using var builder = new SKTextBlobBuilder();
        var run = builder.AllocatePositionedRun(raster, infos.Length);
        Span<ushort> glyphs = run.Glyphs;
        Span<SKPoint> points = run.Positions;
        var clusters = ImmutableArray.CreateBuilder<int>(infos.Length);
        var cursor = 0f;
        for (var i = 0; i < infos.Length; i++) {                          // Exemption: zero-alloc shaped-run fill — GlyphInfos/GlyphPositions array properties recopy, the span accessors do not
            glyphs[i] = (ushort)infos[i].Codepoint;
            points[i] = new SKPoint(cursor + (positions[i].XOffset * scale), -positions[i].YOffset * scale);
            clusters.Add((int)infos[i].Cluster);
            cursor += positions[i].XAdvance * scale;
        }
        return new ShapedRun(builder.Build(), cursor, clusters.MoveToImmutable());
    }
}
```

[ROLE_GRID]:
- Law: a typography role is one frozen row owning every axis both sides read — typeface chain, size, features, cluster level, `Edging`, `Hinting`, `Subpixel`, `LinearMetrics`, synthetic knobs, line-metric policy — and a call site holds a resolved role, never loose font parameters; `LinearMetrics: true` is the layout-stable default for any measured role, because edging, subpixel, and hinting otherwise change advance rounding and drift measurement from drawn pixels.
- Law: line layout derives from `SKFontMetrics`, never constants — `Spacing` is the recommended advance, nullable underline and strikeout metrics project to `Option`, and envelope fields size scroll extents while line fields size baselines; mixing the two families clips ascenders or bloats line boxes.
- Law: fallback is a frozen role × script-class grid probed from packaged faces at catalog freeze — runtime segmentation is a grid lookup; the host `MatchCharacter` probe survives only as the interactive-only tail row, and `SKTypeface.FromFamilyName` is banned at admission because it silently substitutes the nearest host font — `FromData` is the fail-loud route.
- Law: a cell carrying `Embolden` or `SkewX` is a declared receipt that the chain lacks a true face; style matching is nearest-match, so freeze-time enumeration is the only way to distinguish a true style from a substitution, and mixed-chain line metrics come from the role's primary face only — per-run metrics produce ransom-note baselines.
- Law: a role declared shaping-exempt is probed at freeze against its actual character domain — pure ASCII, no features, single face — and `BreakText` plus advance-accumulated positioning are legal only under a proven exemption.

[DOCUMENT_PROJECTION]:
- Law: structured text parses through one immutable pipeline per surface class (`MarkdownPipelineBuilder`, extensions individually admitted) and projects the AST onto the typed render vocabulary, never HTML — one catamorphism with two state channels, a role-delta stack for inlines where `EmphasisInline.DelimiterCount` composes transforms over the active role, and a layout cursor for blocks; an unhandled node family is a total-dispatch compile break.
- Law: extension admission pairs with arm coverage as one checked policy, and `HtmlBlock`/`HtmlInline` are projection-policy rows — verbatim code, drop-with-receipt, or reject — because the render vocabulary has no raw-markup row.
- Law: `LiteralInline.Content` slices travel zero-copy to the shaping boundary; `Markdown.ToPlainText` is the derived secondary projection, never a second parser, and the projection output freezes so a theme swap re-resolves roles without re-parsing while an edit re-projects without re-theming.

## [04]-[ASSET_LAW]

[VECTOR_DOCUMENTS]:
- Law: a vector asset admits once into one document owner — null from `Load`/`FromSvg` is the parse-failure sentinel projected to the rail at admission — and the retained `Picture` is the canonical artifact for every target row, its `CullRect` the recorded intrinsic bounds projected to `Option` for layout instead of rasterized measurements.
- Law: theming is `SvgParameters` (CSS, entities) resolved at admission, never a post-draw color filter — `ReLoad` re-renders from the retained source, building the variant matrix keyed (asset, variant, catalog generation); `SKSvg.CacheOriginalStream` is process-wide pipeline policy declared once, never a call-site write, and with the source cache off the matrix silently degrades to single-variant.
- Law: the cost split is declared per row — picture-only for icons and illustrations, retained scene graph only for hit-testable or animated documents — and evidence-class rows prove provider-resolved text (`Settings.TypefaceProviders`) and script-free source at catalog freeze, with animated documents sampling pinned timestamps, so zero draw-time SVG failure modes survive and render code treats assets as total.
- Law: thumbnail ladders rasterize from vector source at target scale — the `Save` scale pair — never by resampling a master raster.
- Exemption: the dispose-on-failure ownership transfer in the admission body is the platform-forced statement seam.

```csharp conceptual
public readonly record struct VariantKey(string Asset, string Variant, int Generation);

public static class VectorAssets {
    static readonly Atom<HashMap<VariantKey, SKPicture>> Matrix = Atom(HashMap<VariantKey, SKPicture>());
    static VectorAssets() => SKSvg.CacheOriginalStream = true;

    public static Fin<SKSvg> Admit(Stream source) {
        ArgumentNullException.ThrowIfNull(source);
        SKSvg? owner = null;
        try {
            owner = new SKSvg();
            if (owner.Load(source) is null) { return Fin.Fail<SKSvg>(Error.New(7821, "<parse-failure>")); }
            var admitted = owner;
            owner = null;
            return Fin.Succ(admitted);
        }
        finally { owner?.Dispose(); }
    }

    public static Option<SKRect> Intrinsic(SKSvg owner) {
        ArgumentNullException.ThrowIfNull(owner);
        return Optional(owner.Picture).Map(static picture => picture.CullRect);
    }

    public static Fin<SKPicture> Variant(SKSvg owner, VariantKey key, string css) {
        ArgumentNullException.ThrowIfNull(owner);
        return Matrix.Value.Find(key) is { IsSome: true, Case: SKPicture held }
            ? Fin.Succ(held)
            : Optional(owner.ReLoad(new SvgParameters(null, css)))
                .ToFin(Error.New(7822, $"<restyle-failure:{key.Variant}>"))
                .Map(picture => Matrix.Swap(m => m.TryAdd(key, picture)).Find(key).IfNone(picture));
    }
}
```

[ICON_AND_RASTER]:
- Law: icon identity is the (`Symbol`, `IconVariant`) pair end-to-end — a closed glyph enum crossed with an orthogonal variant axis — and the domain catalog derives role-to-pair rows from it; string-keyed registries, path-drawn copies of vocabulary glyphs, and ad-hoc glyph bitmaps are the three rejected forms.
- Law: font-backed icons delete the raster ladder — scale is font size, color is the foreground slot, both token-resolved — and inherit the text determinism axes, so evidence surfaces bearing icons pin exactly what typography pins; the `Color` variant is payload-bearing and ignores tinting by design, so catalog rows mixing it with tint-driven theming mark it.
- Law: raster assets admit through `SKCodec.Create(stream, out SKCodecResult)` — a full taxonomy where `IncompleteInput` is partial success with rows-decoded evidence, never a boolean failure — with `Info` gating shape before allocation, decode landing directly in the pinned working format, and `EncodedOrigin` baked into the artifact so no consumer ever sees pre-rotation pixels.
- Law: asset identity is two keys on one load receipt — the locator names the slot, the content hash names the value — so staleness is hash inequality, derived rasters key on (source hash, derivation row), and a baseline mismatch decomposes into asset drift versus render drift from receipts alone; identity computes at admission, and a pipeline hashing per frame has misplaced the seam.
- Law: animated rasters are codec rows — `FrameCount`, `GetFrameInfo`, `RepetitionCount`, dependency-explicit `SKCodecOptions.FrameIndex`/`PriorFrame` — and the codec never owns a timer: the motion pump schedules the frame table, so animated rasters ride the same reduced-motion and frame-ceiling policy as every moving surface.
- Reject: eager whole-image `SKBitmap.Decode`; loader-local retry loops — the outbound hop already has one retry owner; tier clearing as invalidation — invalidation is an identity comparison, clearing an operational action.

## [05]-[CHART_LAW]

[SERIES_TABLE]:
- Law: a chart is a fold over three data inputs — series-spec table, window artifacts, resolved tokens — so chart state is diffable, snapshotable, and headless-renderable by construction, and a chart that cannot be reproduced from the three has leaked imperative state.
- Law: the series-kind vocabulary is closed and dispatches one spec record — kind, raw values, a `Projection` value map, a paint-token key, one `Geometry` knob each arm binds to its concrete (`LineSeries.GeometrySize`/`LineSmoothness`, `ColumnSeries.Rx`/`Ry`) — onto generated series rows; the evidence posture (`DisableAnimations`, `Lineal`) applies once across arms, never re-spelled per kind, so a new kind is one vocabulary row plus one dispatch arm that breaks at compile time, a new treatment is paint rows, and a new data shape is one `Projection` — no foreseeable chart requirement opens a new surface.
- Law: the headless family mirrors the controls one-to-one on shared generated bases — parity is generated, not maintained — and `InMemorySkiaSharpChart` rows feed chart evidence through `GetImage()` into the render-hash law; the headless rows accept a live view, the parity bridge between what a user saw and what a proof hashes.
- Law: axis rows own scale and chrome together — `Labeler` is the one label projection resolved from locale tokens, `UnitWidth` declares one unit's domain width (the invisible-bars defect on date axes is an unset `UnitWidth`), `MinStep` with `ForceStepToMin` pins tick density, and `DrawMargin` pins plot rectangles where dashboards must align.
- Law: interaction posture is data — `ZoomAndPanMode` flags compose per axis, and `FindingStrategy` declares pointer-to-point mapping consumed identically by tooltips and programmatic queries, so a passing point-query proof certifies interactive behavior — and global policy declares once through `LiveCharts.Configure` at the root, materialized from resolved tokens inside the catalog's publication.

```csharp conceptual
[SmartEnum<string>]
public sealed partial class SeriesKind {
    public static readonly SeriesKind Trend = new("<kind-a>");
    public static readonly SeriesKind Band = new("<kind-b>");
}

public sealed record SeriesSpec(
    SeriesKind Kind, ImmutableArray<double> Values, Func<double, double> Projection, string Paint, double Geometry);

public static class ChartEvidence {
    public static ISeries Materialize(SeriesSpec spec, HashMap<string, SolidColorPaint> paints) {
        ArgumentNullException.ThrowIfNull(spec);
        var projected = spec.Values.Select(spec.Projection).ToArray();
        return spec.Kind.Switch(
            state: (Values: projected, Paint: paints[spec.Paint], spec.Geometry),
            trend: static s => Posed(new LineSeries<double> {
                Values = s.Values, Stroke = s.Paint, Fill = null,
                GeometrySize = s.Geometry, LineSmoothness = 0d,
            }),
            band: static s => Posed(new ColumnSeries<double> {
                Values = s.Values, Fill = s.Paint, Rx = s.Geometry, Ry = s.Geometry,
            }));
    }

    static ISeries Posed<TSeries>(TSeries series) where TSeries : ISeries {
        (series.AnimationsSpeed, series.EasingFunction) = (LiveCharts.DisableAnimations, EasingFunctions.Lineal);
        return series;
    }

    public static SKImage Evidence(Seq<SeriesSpec> table, HashMap<string, SolidColorPaint> paints, Func<double, string> label) =>
        new SKCartesianChart {
            Width = 640, Height = 400, Background = SKColors.White,
            Series = [.. table.Map(spec => Materialize(spec, paints))],
            XAxes = [new Axis { Labeler = label, MinStep = 1d, UnitWidth = 1d, ForceStepToMin = true }],
            YAxes = [new Axis { MinLimit = 0d, MaxLimit = 10d }],
        }.GetImage();
}
```

[STREAM_BINDING]:
- Law: a chart binds to a fold artifact, never a producer — a fixed window or downsampled projection computed in the stream lane, with lanes, backpressure, and drop receipts arriving settled from the throughput layer — and the two mutation grains never mix on one series: in-place entity mutation inside a stable pre-allocated window for high-frequency feeds, atomic collection swap for structural change; rebuilding collections per tick is the canonical live-chart defect.
- Law: downsampling is upstream and explicit — at most ~2 points per rendered pixel column, a min/max pair per bucket preserving the envelope extremes averaging destroys — with bucket width derived from declared `MinStep` and `UnitWidth`, never guessed from render width.
- Law: live and evidence charts ride the motion disable row (`LiveCharts.DisableAnimations`), and streaming axis limits are pinned or hysteresis-banded in the stream fold, so the frame-to-frame diff is data motion, never scale motion.
- Law: `SyncContext` is the chart-side declaration of the marshaled-input guarantee; window artifacts are value snapshots — a saved window plus its spec plus the catalog generation re-renders bit-identical evidence, so live-chart forensics is replay of values, never reproduction of timing.

## [06]-[TOKEN_ALGEBRA]

[MASTER_SHAPE]:
- Law: five concerns — theme paints, typography roles, motion rows, locale rows, icon rows — are one algebra differing only in row payload: a frozen total (role × variant × density) grid, one pure resolve fold to an immutable resolved-artifact record, one atomic swap publishing (generation, changed keys, causing axis); a sixth tokenized concern is one new instantiation with zero new mechanism.
- Law: consumers mount against keys and hold resolved artifacts — every pigment, type, duration, and easing payload is minted only inside the resolve fold, so the literal-at-call-site audit is grep-shaped and a key that fails to resolve is a freeze-time rejection, never a runtime path.
- Law: the grid is total at freeze — a missing cell is a construction rejection, never a draw-time fallback chain — and density is an axis, not a scale factor: compact and comfortable rows carry distinct stroke, spacing, and type-size payloads because optical correctness does not scale linearly, and the cell count is the honest price totality makes safe to pay.
- Law: the resolved payload is a value-semantic record, never a live native — the paint payload is the full pigment row (float color with color-space tag, stroke metrics, effect slots) carrying generated structural equality, and the live `SolidColorPaint`/`ColorPaletteResources` mints from it at the binding edge; the `IEquatable<TPayload>` bound makes the diff genuine value equality, so two distinct cells resolving an identical pigment emit nothing and a reference-typed payload — whose default equality is per-instance — silently emitting every key on every swap is the foreclosed defect.
- Law: the changed-key set bounds re-mount work while the causing-axis field routes partial subscription, so one swap moves raw canvas and chart surfaces through one receipt and a content-identical flip is a zero-key no-op.
- Law: generation stamps unify staleness — shaped-run caches, vector variant matrices, ramp tables, and chart paints all key on catalog generation, so cross-cache coherence is one integer's monotonicity — and the catalog is one process-wide instance, because per-window catalogs fork the stamp and desynchronize derived caches.
- Boundary: theme application — variant binding, density switching, template consumption — is interaction law; this algebra's deliverables end at the resolved record and the diff receipt.
- Reject: cascade resolution as the canvas theming substrate — dictionary chains resolve per element per pass, and the fold's held output is both the determinism and the performance win.

```csharp conceptual
public sealed record Resolved<TPayload>(int Generation, string Axis, HashMap<string, TPayload> Artifacts);
public sealed record Catalog<TPayload>(
    FrozenDictionary<(string Role, string Variant, string Density), TPayload> Grid, Seq<string> Roles) {
    public static Fin<Catalog<TPayload>> Freeze(
        Seq<string> roles, Seq<string> variants, Seq<string> densities,
        Func<(string Role, string Variant, string Density), Option<TPayload>> mint) =>
        roles.Bind(role => variants.Bind(variant => densities.Map(density => (Role: role, Variant: variant, Density: density))))
            .TraverseM(key => mint(key).ToFin(Error.New(7841, $"<missing-cell:{key}>")).Map(payload => (key, payload))).As()
            .Map(cells => new Catalog<TPayload>(
                cells.AsEnumerable().ToFrozenDictionary(static cell => cell.key, static cell => cell.payload), roles));

    public HashMap<string, TPayload> Resolve(string variant, string density) =>
        toHashMap(Roles.Map(role => (role, Grid[(role, variant, density)])));
}

public sealed class TokenAlgebra<TPayload>(Catalog<TPayload> catalog, string variant, string density)
    where TPayload : IEquatable<TPayload> {
    readonly Atom<Resolved<TPayload>> cell = Atom(new Resolved<TPayload>(0, "<boot>", catalog.Resolve(variant, density)));

    public Resolved<TPayload> Current => cell.Value;

    public (int Generation, Seq<string> Changed, string Axis) Swap(string axis, string nextVariant, string nextDensity) {
        var (next, prior) = (catalog.Resolve(nextVariant, nextDensity), Current);
        var generation = cell.Swap(held => new Resolved<TPayload>((prior = held).Generation + 1, axis, next)).Generation;
        var changed = toSeq(next.Filter((key, value) =>
            prior.Artifacts.Find(key).Map(was => !value.Equals(was)).IfNone(true)).Keys);
        return (generation, changed, axis);
    }
}
```

## [07]-[MOTION_AND_COLOR]

[MOTION_ROWS]:
- Law: a motion token is a (duration, easing) row in the same frozen algebra — easing payloads are pure unit-interval functions, property-checked at freeze: monotone where declared, endpoint-exact, bounded overshoot — and one easing vocabulary serves charts and visual motion alike, so two easing tables in one system is the rejected form.
- Law: the sentinel system is vocabulary — the disable row is the one-millisecond constant and the unset marker means inherit — so treating zero as off or max-value as very slow misreads both, and admission normalizes raw durations through the vocabulary.
- Law: reduced motion is an axis, not a flag check — the reduced variant degrades durations to the sentinel and easing to linear, perceivable state changes degrade to opacity-only rows rather than disappearing, and the platform preference admits once at the boundary and republishes through the standard diff receipt with zero call-site conditionals.
- Law: bespoke curves are keyframe-table and parameterized-builder rows, never hand-written interpolation functions, and motion cost is auditable from declarations — the frame ceiling times per-row durations yields the worst-case redraw budget per swap before any frame renders.

[PERCEPTUAL_LAW]:
- Law: color motion and ramp generation are `Unicolour.Mix`/`Palette` over a `ColourSpace` row, never a hand-rolled lerp or local opponent-space transform — the package owns the cube-root LMS matrices, the desaturation-free midpoint, and the hue path, so the interpolation space is a policy row (`ColourSpace.Oklab` for perceptual distance, `ColourSpace.Oklch` plus a `HueSpan` for long-hue-distance tweens) and the componentwise-sRGB lerp that bends hue through the gray dead zone is the deleted form.
- Law: gamut mapping is `GamutMap.OklchChromaReduction` reached through `Palette`/`Mix` and the `IsInRgbGamut` gate, never an RGB clamp — clamping shifts lightness and hue and reintroduces exactly the artifacts perceptual interpolation removed — and `premultiplyAlpha` on the mix is the alpha contract the render lane's premultiply boundary reads, so alpha never interpolates in a second hand-written pass.
- Law: ramps and endpoints compute at token resolution into precomputed `Unicolour` stop tables sized by perceptual step — motion samples the projected `.Rgb` table and per-frame reconversion is waste — and the achromatic-endpoint and near-neutral hue-flicker edges are the package's mix concern, named once as the reason the tween carries endpoints rather than a hand-neutralized scalar.
- Law: sequential ramps assert trend-signed monotonic `.Oklab.L` over the generated palette and diverging ramps pin a neutral pivot through one ramp builder discriminating on pivot presence, so a perceptually broken palette is a freeze-time construction failure rather than a chart-reading hazard, and text-bearing roles assert their paired `Contrast` ratio at freeze through the same model rather than a re-derived luminance.
- Law: motion and color converge in one tween row — motion token plus the resolved stop table — where the table is the artifact and the index-clamped sampler the only code, clamped because declared-overshoot easings legally exceed the unit interval; the reduced variant's degenerate tween is a one-stop table that still resolves through the same gamut-mapped mix.

```csharp conceptual
public sealed record MotionToken(TimeSpan Duration, Func<float, float> Easing) {
    public static readonly TimeSpan Disable = TimeSpan.FromMilliseconds(1);
    public static readonly MotionToken Reduced = new(Disable, EasingFunctions.Lineal);
}

public sealed record TweenRow(MotionToken Motion, ImmutableArray<SKColor> Table) {
    public SKColor Sample(float t) =>
        Table[int.Clamp((int)(Motion.Easing(float.Clamp(t, 0f, 1f)) * (Table.Length - 1)), 0, Table.Length - 1)];
}

public static class Ramps {
    public static Fin<TweenRow> Build(
        MotionToken motion, Unicolour from, Unicolour to, int stops, Option<Unicolour> pivot = default) =>
        Stops(from, to, stops, pivot)
            .Bind(seq => double.Sign(to.Oklab.L - from.Oklab.L) is var trend
                      && seq.Zip(seq.Skip(1)).ForAll(pair => trend * (pair.Second.Oklab.L - pair.First.Oklab.L) >= 0)
                ? Fin.Succ(seq)
                : Fin.Fail<Seq<Unicolour>>(Error.New(7861, "<non-monotonic-lightness>")))
            .Map(seq => new TweenRow(motion, [.. seq.Map(Quantize)]));

    static SKColor Quantize(Unicolour colour) =>
        new(red: (byte)colour.Rgb.Byte255.Clipped.R, green: (byte)colour.Rgb.Byte255.Clipped.G,
            blue: (byte)colour.Rgb.Byte255.Clipped.B, alpha: (byte)colour.Alpha.A255);

    static Fin<Seq<Unicolour>> Stops(Unicolour from, Unicolour to, int stops, Option<Unicolour> pivot) =>
        pivot is { IsSome: true, Case: Unicolour mid }
            ? Stops(from, mid, (stops + 1) >> 1, None).Bind(rise =>
                Stops(mid, to, (stops + 2) >> 1, None).Map(fall => rise.Concat(fall.Tail)))
            : Fin.Succ(toSeq(from.Palette(to, ColourSpace.Oklch, int.Max(stops, 2), HueSpan.Shorter)));
}
```
