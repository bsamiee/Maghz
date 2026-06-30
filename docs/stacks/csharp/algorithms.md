# [ALGORITHMS]

Numeric work is admitted once and routed by shape: raw operands cross into a finite-checked owner at one boundary, the interior is total over admitted values, and the operand's structure — definite, square, overdetermined, symmetric, sparse-pattern, periodic-grid — selects the owning factorization, never the call site and never a knob riding beside the matrix. Every solve route — dense direct, sparse direct, iterative, every conditioning fallback — is one composed lifecycle admit → route → solve → witness → receipt written once; a per-module pipeline re-deriving the chain is the rejected form.

MathNet owns dense factorization, the spectral decompositions, `Fourier`, and quadrature; CSparse owns sparse direct factorization, factor reuse, and fill-reducing ordering; the owned-build lane — low-discrepancy sampling, ODE tableaux, spectral multipliers, block eigeniteration, scattered reconstruction — has no library surface and is composed from the rails. A hand-rolled kernel is admitted only after a benchmark defeats both libraries.

Every library refuses its own gates — no constructor checks finiteness, symmetry is tested by exact `!=`, singularity is never asserted, a zero-norm `QR` fills `NaN` while `IsFullRank` returns `true` — so admission re-imposes each refused gate as an explicit predicate. Every result leaves as a domain receipt carrying its route variant, its scale-derived tolerance policy, and the recomputed true relative residual against the original operator — the one correctness signal surviving preconditioning, breakdown substitution, cancellation, and provider divergence — never a `Matrix<T>`, `Vector<T>`, or factorization instance. In-place numeric kernels — library in-place solve and multiply overloads writing into pre-sized scratch, and per-evaluation counters inside guarded integrands — are this page's named statement exemption.

## [01]-[ROUTE_SPINE]

The operand shape selects the route before any solve; the most specific shape wins, and the table is the lifecycle's one route step.

| [INDEX] | [OPERAND_SHAPE]                        | [OWNING_ROUTE]                        | [CONDITIONING_FALLBACK]                |
| :-----: | :------------------------------------- | :------------------------------------ | :------------------------------------- |
|  [01]   | dense symmetric positive-definite      | `Cholesky()`                          | `ε·I` shift, then `Evd`                |
|  [02]   | dense square general                   | `LU()`                                | rank-revealing `Svd(true)`             |
|  [03]   | dense overdetermined                   | thin `QR()`                           | `Svd(true)` truncated pseudo-inverse   |
|  [04]   | tiny system below sparse crossover     | dense factorization-as-probe          | managed path beats provider switch     |
|  [05]   | symmetric or Hermitian spectrum        | `Evd(Symmetricity.Symmetric)`         | congruence-reduced generalized `Evd`   |
|  [06]   | nonsymmetric spectrum                  | `Evd(Symmetricity.Unknown)`           | block residual witness, no resort      |
|  [07]   | rank, norm, or condition evidence only | retained `Svd(false)` handle          | one handle answers all three           |
|  [08]   | sparse SPD, fixed pattern              | `SparseCholesky` + `AMD`              | rank-1 downdate fails → reconstruct    |
|  [09]   | sparse symmetric indefinite            | `SparseLDL`                           | `BiCgStab` while structure unproven    |
|  [10]   | sparse nonsymmetric or uncertain       | `SparseLU` (column-relative `tol`)    | iterative solve + witness gate         |
|  [11]   | sparse rectangular least-squares       | `SparseQR`                            | augmented-dimension solution sizing    |
|  [12]   | huge sparse or changing pattern        | `TrySolveIterative` + criterion stack | verdict-routed direct solve            |
|  [13]   | constant-coefficient periodic grid     | owned spectral multiplier             | regularization at the vanishing symbol |

Recover the fallback from the route value and record the taken path in the receipt, never a caller-named entrypoint; primary and conditioning routes rebind onto the one lifecycle and converge on the one witness gate. A fill ratio — symbolic factor nonzeros over input nonzeros, read before the numeric sweep — routes direct versus iterative, and the augmented regression case (the design matrix stacked over a `√λ`-scaled identity under thin `QR`) is the derived consequence of the conditioning budget exceeding the inverse cap. MathNet exposes no CSparse surface, so hybrid routing is integrator-authored and carries its own residual validation.

[ROUTE_VOCABULARY]:
- Law: the route is one `[SmartEnum]` whose items span every operand shape the table lists — dense definite, square, overdetermined, spectral, evidence; sparse Cholesky, LDL, LU, QR; iterative; spectral-grid — keyed for the receipt, so a new substrate is one `static readonly` item and every `Route`-keyed projection gains one row with the `Switch` over the items broken loudly at compile time. The operand is the spine's own admitted `Matrix<double>` argument, never an item payload, because every route carries the identical operator shape; what varies per route is carrier-invariant behavior, carried as constructor columns — the `Scale` the tolerance derives from, the `Conditioned()` fallback route, and the sparse capability columns the `[04]` grid declares — while the carrier-specific factorization builder rides the boundary table the next law fixes.
- Law: the conditioning fallback is a `[UseDelegateFromConstructor]` `Conditioned()` column read off the item — the definite item points it at the spectral item, the square at the rank-revealing, a route with no harder fallback at itself — so primary and conditioning routes are one vocabulary the spine rebinds through one `BindFail`, dense and sparse alike, never the `DenseRoute`-only combinator that leaves the sparse rank-1-downdate-to-reconstruct fallback uncomposed; the deferred `static () => Spectral` is the forward-reference guard, since a field initializer reading a later item captures `null` before materialization.
- Law: the factorization builder is the ONE legitimate split from the route vocabulary — a `FrozenDictionary<Route, Func<Matrix<double>, ISolver<double>>>` minted once at the compute boundary, keyed on the same route — because the dense `Cholesky()`/`LU()`/`QR(QRMethod.Thin)`/`Evd(Symmetricity)`/`Svd(true)` factory over `Matrix<double>` and the sparse factory over `CompressedColumnStorage<double>` cannot share one delegate signature, so the carrier-specific builder rides the boundary table while the carrier-invariant `Scale`, capability, and `Conditioned` columns ride the route; the `QRMethod.Thin`-over-`Full` and `Symmetricity` discriminants bake into the dense factory at declaration, never a `bool computeVectors`/`QRMethod`/`Symmetricity` parameter riding loose beside the matrix.
- Law: collapse the built-in absolute, magnitude-squared, and scale-relative rank-tolerance thresholds into the one scale-derived `Scale` column `[03]` carries, never a fourth column re-deciding it; the element carrier is monomorphic `double`, and the `struct, IEquatable<T>, IFormattable` family excludes `INumber<T>`, so a generic-math route signature is decorative.
- Reject: a `FactorRoute` `[Union]` whose cases each carry one identical `Matrix<double>` and whose `Operator =>` switch projects the same field from every arm — a uniform-payload tagged union the operand-as-argument plus a `Route` key is denser than; a parallel `FactorKind` `[SmartEnum]` beside it splitting the sparse capability grid from the dense route so a new route detonates in a different owner depending on density; a sixth sibling factory; a second route-keyed table per carrier-invariant behavior axis where one route column carries it.

```csharp conceptual
[SmartEnum<string>]
public sealed partial class Route {
    public static readonly Route DefinitePsd     = new("<route-a>", Scale.OperatorRhs, rank1Edit: true,  inertia: false, reentrant: false, transposeSolve: false, static () => Spectral);
    public static readonly Route SquarePivoting  = new("<route-b>", Scale.OperatorRhs, rank1Edit: false, inertia: false, reentrant: false, transposeSolve: true,  static () => RankRevealing);
    public static readonly Route Overdetermined  = new("<route-c>", Scale.SingularDim, rank1Edit: false, inertia: false, reentrant: true,  transposeSolve: true,  static () => RankRevealing);
    public static readonly Route Spectral        = new("<route-d>", Scale.OperatorRhs, rank1Edit: false, inertia: true,  reentrant: false, transposeSolve: false, static () => Spectral);
    public static readonly Route RankRevealing   = new("<route-e>", Scale.SingularDim, rank1Edit: false, inertia: false, reentrant: false, transposeSolve: false, static () => RankRevealing);
    public static readonly Route SparseCholesky  = new("<route-f>", Scale.OperatorRhs, rank1Edit: true,  inertia: false, reentrant: false, transposeSolve: false, static () => Spectral);
    public static readonly Route SparseLu        = new("<route-g>", Scale.OperatorRhs, rank1Edit: false, inertia: false, reentrant: false, transposeSolve: true,  static () => SparseLu);

    public Scale Scale { get; }
    public bool Rank1Edit { get; }
    public bool Inertia { get; }
    public bool Reentrant { get; }
    public bool TransposeSolve { get; }

    [UseDelegateFromConstructor] public partial Route Conditioned();
}

public static class DenseRoute {
    static readonly FrozenDictionary<Route, Func<Matrix<double>, ISolver<double>>> Build =
        new KeyValuePair<Route, Func<Matrix<double>, ISolver<double>>>[] {
            new(Route.DefinitePsd,    static a => a.Cholesky()),
            new(Route.SquarePivoting, static a => a.LU()),
            new(Route.Overdetermined, static a => a.QR(QRMethod.Thin)),
            new(Route.Spectral,       static a => a.Evd(Symmetricity.Symmetric)),
            new(Route.RankRevealing,  static a => a.Svd(computeVectors: true)),
        }.ToFrozenDictionary();

    public static Fin<Vector<double>> Solve(Route route, Matrix<double> operand, Vector<double> b, double cap) =>
        Admit(operand)
            .Map(Build[route])
            .Map(solver => solver.Solve(b))
            .Bind(x => Witness.Gate(route.Key, Witness.Residual(operand, x, b), cap).Map(_ => x))
            .BindFail(_ => route.Conditioned() is var next && next != route
                ? Solve(next, operand, b, cap)
                : Fin.Fail<Vector<double>>(Error.New(2099, $"<exhausted:{route.Key}>")));
}
```

## [02]-[ADMISSION_GATES]

[FINITE_ADMISSION]:
- Law: gate every operand on one all-finite predicate over the flat column-major `Values` span before factoring, with NaN-any and Inf-any early-exit variants when the typed rejection must name its cause.
- Reject: a strided per-element loop; it forfeits the one-pass vectorized admission the column-major layout grants.

```csharp conceptual
public static class Admission
{
    public static Fin<double[]> Admit(double[] flat) =>
        TensorPrimitives.IsFiniteAll<double>(flat)
            ? Fin.Succ(flat)
            : TensorPrimitives.IsNaNAny<double>(flat)
                ? Fin.Fail<double[]>(Error.New(2101, "operand carries NaN"))
                : Fin.Fail<double[]>(Error.New(2102, "operand carries Inf"));

    public static Fin<DenseMatrix> Admit(DenseMatrix a) => Admit(a.Values).Map(_ => a);

    public static Fin<DenseVector> Admit(DenseVector v) => Admit(v.Values).Map(_ => v);
}
```

[SYMMETRY_FORCING]:
- Law: force symmetry with `(A + A.Transpose()) * 0.5` before the call (`ConjugateTranspose` for Hermitian); `IsSymmetric()` compares entries with exact `!=`, so accumulation-built matrices fail it and route `Symmetricity.Unknown` to the asymmetric solve that throws.
- Reject: `MapIndexedInplace` self-averaging; it mutates the backing array sequentially, so a mirror entry is already modified when read.
- Boundary: a one-ULP mirror difference silently acquires the full nonsymmetric contract — block-diagonal `D`, non-orthonormal columns, spurious complex pairs.
- Law: symmetrize before the definite kernel, which reads only the upper triangle, never substitute a separate eigenvalue probe.

[SINGULAR_AND_ZERO_NORM]:
- Law: probe the factor diagonal for near-zero entries, since `LU()` on a singular input yields `Determinant == 0.0` and never throws.
- Law: read singularity from the streaming log-determinant `2·Σ log L[i,i]`; the determinant product underflows to zero with no signal and the plain determinant's logarithm is `−Inf`.
- Law: test reflection as `det < 0.0`, never `det != 1.0`, since a rotation's determinant is only approximately ±1.
- Law: check the factor buffers all-finite after a `QR` construction; a near-zero column norm divides through and fills `Q`/`R` with `NaN` while `IsFullRank` still returns `true`, the throw firing only at a bit-exact-zero norm.
- Use: thin Householder `QR` over single-pass Gram-Schmidt in near-dependent columns; the probe `qr.R.Diagonal().Any(v => Math.Abs(v) < floor)` lazily materializes `R`.

## [03]-[DENSE_FACTOR_LAW]

[RANK_AND_TOLERANCE]:
- Law: every threshold is one of two scale-derivation forms closed in the `Scale` `[SmartEnum]` the `[01]` route column carries — `OperatorRhs` is `ε·‖A‖_F·max(‖b‖∞, 1)` for a square solve, `SingularDim` is `ε·σ_max·max(m, n)` for the least-squares rank floor reading `σ_max` off the held `Svd` — each a `[UseDelegateFromConstructor]` `Derive(Matrix<double>, Vector<double>) -> double` column, so the derivation is the route's own policy axis projected once at the witness terminus and travelled as the gated tolerance on the receipt, never a per-route table whose square and definite rows duplicate one body.
- Reject: a bare per-module absolute literal in `1e-4..1e-8`; it is unreplayable and uncomparable across operators, and a fresh literal per call site is the same defect spelled inline.
- Law: carry the `Svd<T>.Rank` (`σ_max.EpsilonOf() · max(m, n)`) as the conditioning rank; never share its slot with `Evd<T>.Rank` (`AlmostEqual` at `DefaultDoubleAccuracy`), and treat any spectral rank as a definiteness signature only.
- Law: recompute domain rank as `n − count(|λᵢ| < ε_rank · max|λⱼ|)` with a caller-supplied spectral-radius-relative `ε_rank`; the built-in absolute `|λ| < ~3.33e-8` zero test misclassifies significant eigenvalues for `‖A‖₂ ~ 10⁶`.
- Law: build validity predicates on `EpsilonOf(value)` and store the pre-computed residual diff beside the threshold; `value * DoublePrecision` diverges at binade boundaries (`EpsilonOf(2.5) = 2⁻⁵¹` versus `6.95e-16`), and `AlmostEqualNormRelative` hides relative, absolute-on-tiny, and absolute-on-zero behind `IsRelative: true`.
- Boundary: guard `ConditionNumber` against `+Inf` before gating; it is `+Inf` for rank-deficient operators.

[HELD_HANDLE]:
- Law: retain one `Svd(false)` handle for rank, `L2Norm`, and `ConditionNumber`; each base-matrix query otherwise builds a fresh cubic decomposition, while the cheap induced norms stay quadratic provider reductions touching no decomposition.
- Law: stream N right-hand sides through one held factorization as N triangular solves into the in-place overload; the allocating overload appears only where a value leaves the boundary, never a loop of fresh factorizations.
- Use: the definite handle's in-place block-copy privilege to refactor a streaming operator; every other handle demands a fresh construction per operand, the controlling cost at small `n`.
- Reject: `Inverse()` in a hot loop — it clones the factors plus an `n²` identity, crossing the large-object threshold at `n ≥ 104`; solve against an identity through the retained pivoting handle with reused result and right-hand-side buffers.
- Law: refinement is a bounded fixpoint, not a `Schedule` — the iteration count is the budget cap, the step is idempotent past tolerance (a converged state re-emits itself), and `Range(0, cap).Fold` over the foldable `Range<int>` retires the `for` counter; `Schedule` is retry-or-repeat policy and `.Run()` yields delay `Duration`s, never a refinement loop driver.
- Boundary: form the residual against the original operator in working precision, never against reconstructed factors — the factors carry exactly the rounding error the correction exists to cancel.

```csharp conceptual
[SmartEnum]
public sealed partial class Scale {
    public static readonly Scale OperatorRhs = new(OperatorRhsForm);
    public static readonly Scale SingularDim = new(SingularDimForm);

    [UseDelegateFromConstructor] public partial double Derive(Matrix<double> a, Vector<double> b);

    static readonly double Eps = Precision.DoublePrecision;
    static double OperatorRhsForm(Matrix<double> a, Vector<double> b) => Eps * a.FrobeniusNorm() * double.Max(b.InfinityNorm(), 1.0);
    static double SingularDimForm(Matrix<double> a, Vector<double> b) => Eps * a.Svd(computeVectors: false).S[0] * double.Max(a.RowCount, a.ColumnCount);
}

public static class HeldRefinement
{
    public static Fin<(IterationStatus Verdict, Vector<double> X)> Refine(
        Matrix<double> a, ISolver<double> held, Vector<double> b, Vector<double> x, double tol, int cap)
    {
        var (bNorm, scratch, dx) = (b.L2Norm(), Vector<double>.Build.Dense(b.Count), Vector<double>.Build.Dense(b.Count));
        var settled = Range(0, cap).Fold(x, (state, _) =>
            Residual(a, state, b, scratch, bNorm) <= tol
                ? state
                : (held.Solve(scratch, dx), state.Add(dx, state)).Item2);
        return Residual(a, settled, b, scratch, bNorm) is var r && double.IsFinite(r)
            ? Fin.Succ((r <= tol ? IterationStatus.Converged : IterationStatus.StoppedWithoutConvergence, settled))
            : Fin.Fail<(IterationStatus, Vector<double>)>(Error.New(2110, $"refinement residual non-finite: r={r}"));
    }

    static double Residual(Matrix<double> a, Vector<double> x, Vector<double> b, Vector<double> scratch, double bNorm)
    {
        a.Multiply(x, scratch);
        b.Subtract(scratch, scratch);
        return scratch.L2Norm() / bNorm;
    }
}
```

[GRAM_WEIGHTING]:
- Law: apply weighting as one policy row through the typed diagonal operand — its fast path scales each row with no `m×n` intermediate — never per-module `√`-weight row scaling re-derived before each Gram.
- Reject: a raw-array weight; it has no fast path and forfeits the structural route.
- Law: select the damped normal form and the augmented `√λ`-stacked form as two cases of one route on a conditioning-budget field; the Gram-plus-ridge form squares `κ` through the densifying transpose-multiply, and the stacked-identity thin `QR` avoids the squaring when condition exceeds the inverse cap.

## [04]-[SPARSE_DIRECT_LAW]

[CSC_OWNER]:
- Law: own one `CompressedColumnStorage<T>`; convert triplet exactly once and derive the row orientation by one `Transpose` at construction, never reconverting among the three formats at runtime.
- Reject: `inplace: true` conversion when the triplet must survive a structural-edit increment; it calls `Invalidate()`, nulling arrays and dangling references.
- Boundary: the row-format bridge factory accepts column-format arrays without type rejection but with transposed semantics, yielding silently wrong preconditioner factors.
- Boundary: run strict storage validation before factoring; it returns `bool` and never throws, and factorizing invalid storage produces silently incorrect factors.

[FILL_AND_ORDERING]:
- Law: read the symbolic factor nonzeros before the numeric sweep to route direct versus iterative; the count is per-kind — one factor for the symmetric kinds, an `L + U − n` sum for `SparseLU`, a `Q + R − m` sum for `SparseQR` — so a bare fill integer compared across kinds is meaningless.
- Law: cache the `AMD.Generate` permutation `int[]` as the value-only refactor key over an invariant pattern.
- Boundary: no entrypoint accepts a prebuilt symbolic record plus fresh values, so the durable reuse unit is the whole factorization reconstructed with the cached permutation.
- Boundary: drop assembly residue with a structural tolerance near `machineEps · ‖A‖_F`; `DropZeros()` defaults to `0.0` and removes only binary zeros, while `CoordinateStorage.At` skips exact-zero contributions so the post-assembly count is the nonzero count.

[KIND_CAPABILITY]:
- Law: the sparse kinds are the `[01]` `Route` items keyed `SparseCholesky`, `SparseLdl`, `SparseLu`, `SparseQr` — the SAME vocabulary the dense routes inhabit, carrying the SAME capability columns the `ISolver<T>` forward-solve seam hides: rank-1 edit, inertia, reentrancy, and transpose-solve are the `Route` `bool` columns the grid below populates, so a request needing edit plus transpose reads the column off the route, never a parallel `FactorKind` `[SmartEnum]` re-declaring the 4×4 grid beside the dense route and forfeiting the single receipt discriminant.
- Law: the transpose-solve behavior binds to the concrete `Inner` instance, so the route carries only the `TransposeSolve` capability column while the operator value resolves the instance-bound `Action<double[], double[]>` gated on it through `(route.TransposeSolve, Inner) switch`; the singleton route item is instance-free and cannot close over a factor.
- Reject: a bare `enum FactorKind` plus an external `switch` — it scatters the capability grid across call sites and forfeits the column the vocabulary owns; a typed-only catch at the factorization boundary, since SPD pivot loss and the zero-diagonal break throw bare `Exception`, not the numerical-breakdown type, so the boundary catches broadly and converts.
- Boundary: an asymmetric input to a symmetric kind factors as its symmetrization and returns a correct answer to the wrong system — the post-solve true residual is the only structural signal.
- Boundary: set the `SparseLU` pivot `tol` in `[0, 1]` as a relative column threshold — `1` full partial pivoting, `0` disabled — never an absolute floor.

| [SPARSE_ROUTE]         | [RANK1_EDIT] | [TRANSPOSE_SOLVE] | [INERTIA] | [REENTRANT] |
| :--------------------- | :----------: | :---------------: | :-------: | :---------: |
| `SparseCholesky` SPD   |     yes      |        no         |     —     |     no      |
| `SparseLDL` symmetric  |      no      |        no         |  private  |     no      |
| `SparseLU` unsymmetric |      no      |        yes        |     —     |     no      |
| `SparseQR` rectangular |      no      |        yes        |     —     |     yes     |

[FACTOR_CACHE]:
- Law: collapse a completed factorization to one typed operator value owning the factorization instance, cached permutation, symbolic fill counts, solution dimension, and the `Route` discriminant — the same vocabulary the dense spine reads, so the capability columns ride the route, never a second `FactorKind` field beside it.
- Law: the solve returns a bare vector with no status, so the post-solve residual witness against the original operator belongs to the operator value, never the call site; the sparse builder is the carrier-specific factory injected at this compute boundary because the dense `Build(Matrix<double>)` column and the sparse `CompressedColumnStorage<double>` factory cannot share one delegate signature — the one legitimate split from the `Route` vocabulary, gated off-wheel.
- Law: key the cache on dimensions, sparsity fingerprint (hash of the pointer and index arrays), and ordering identity.
- Law: populate the cache success-only so only residual-witnessed factorizations enter and a diverged solve never poisons reuse.
- Boundary: serialize solves on a cached square factorization — its one constructor-allocated scratch is non-reentrant and a concurrent second solve corrupts both results with no guard — through a capsule owning the factorization or a pattern-keyed instance pool.
- Boundary: size the rectangular kind's work buffer from the factorization's solution dimension, which exceeds the row count for structurally singular systems; sizing from the matrix shape is the off-by-augmentation fault.

```csharp conceptual
public sealed record FactoredOp(
    ISparseFactorization<double> Inner, Route Kind, CompressedColumnStorage<double> A,
    int[] Permutation, int Fill, int SolutionDim) {
    public bool SharesScratch => !Kind.Reentrant;

    public Option<Action<double[], double[]>> TransposeColumn => (Kind.TransposeSolve, Inner) switch {
        (true, SparseLU lu) => Some<Action<double[], double[]>>(lu.SolveTranspose),
        (true, SparseQR qr) => Some<Action<double[], double[]>>(qr.SolveTranspose),
        _ => None,
    };

    public Fin<double[]> Solve(double[] b, double cap) {
        var x = new double[SolutionDim];
        Inner.Solve(b, x);
        return Witness.Gate($"route={Kind.Key} fill={Fill}", Witness.Residual(A, x, b), cap).Map(_ => x);
    }

    public FactoredOp Revalue(double tol) => this with { Inner = SparseLU.Create(A, Permutation, tol) };
}
```

[STRUCTURAL_EDIT]:
- Law: express every structural-edit dialect — pin, prune, rank-1 bump, revalue — as one `Edit` `[Union]` over three primitives: predicate compaction for removal, marker-array scatter for additive merge, tree-path walk along `parent[]` for symmetric rank-1 change.
- Law: discard and reconstruct on a `false` rank-1 result; the partial walk has already corrupted the factor, so a retry compounds corruption.
- Law: route a non-symmetric change to reconstruction regardless of magnitude.
- Boundary: batch more than one structural insertion through triplet accumulation plus a single re-conversion — each in-place insertion shifts the suffix at `O(nnz)` — and suppress the process-global exact-fit trim flag for the whole sequence, restoring it once.

```csharp conceptual
[Union]
public abstract partial record Edit
{
    public sealed partial record Pin(int Node) : Edit;
    public sealed partial record Prune(double Tolerance) : Edit;
    public sealed partial record Bump(int Sign, double[] Column) : Edit;
    public sealed partial record Revalue(double[] Values) : Edit;
}

public static class StructuralEdit
{
    public static Fin<FactoredOp> Apply(FactoredOp op, Edit edit) => edit switch
    {
        Edit.Bump b when op.Kind.Rank1Edit =>
            op.RankOne(b.Sign, b.Column)
                ? Fin.Succ(op)
                : Rebuild(op, edit),
        Edit.Revalue r => Fin.Succ(op with { Inner = Refactor(op.Permutation, r.Values) }),
        var structural => Rebuild(op, structural),
    };
}
```

## [05]-[ITERATIVE_AND_WITNESS]

[CRITERION_PRECEDENCE]:
- Law: construct the criterion stack explicitly in order `FailureStopCriterion`, `DivergenceStopCriterion`, `ResidualStopCriterion`, `IterationCountStopCriterion`, since insertion order is precedence; `Failure` first keeps `NaN` terminal and `Residual` before the count cap suppresses convergence on the final iteration.
- Law: size the count ceiling as a multiple of the expected Krylov dimension; a `null` iterator silently substitutes a hardcoded `1000`-iteration cap.
- Law: set the residual threshold relative to `‖b‖∞`; an absolute residual floor misreads operator scale.
- Boundary: key the divergence window length on the operator's symmetry class; short windows fire spuriously through the non-symmetric oscillatory warm-up.

[BREAKDOWN_AND_WITNESS]:
- Law: treat recovery as a solver-kind property; the same near-zero inner-product denominator throws in one nonsymmetric solver, cancels the iterator in a second, and substitutes `1` and continues in a third, so swapping solvers swaps failure semantics with no call-site difference.
- Reject: the substitution path as the most dangerous — it certifies an arbitrary iterate under a normal verdict, and the ULP guard fails open on `NaN`.
- Law: admit an iterate only on the independently recomputed true relative residual against the original operator; the converged verdict certifies only that the preconditioned residual fell below tolerance, and left preconditioning distorts the norm.
- Reject: the composite solver's externally passed preconditioner — its constructor resolves each setup's preconditioner internally, making the argument dead code.
- Boundary: initialize each preconditioner outside the solve and catch its throw there; the init throw otherwise escapes the verdict-returning entrypoint and leaves stale buffer content reading as an answer.
- Boundary: route divergence to a regularized retry or direct solve.
- Boundary: route count-exhaustion to a direct solve seeded with the partial iterate.

```csharp conceptual
public static class Iterative
{
    static Iterator<double> Stack(int dim, double tol, bool symmetric) =>
        new(new IIterationStopCriterion<double>[]
        {
            new FailureStopCriterion<double>(),
            new DivergenceStopCriterion<double>(0.08, minimumIterations: symmetric ? 3 : 10),
            new ResidualStopCriterion<double>(tol),
            new IterationCountStopCriterion<double>(8 * dim),
        });

    public static Fin<Vector<double>> Solve(
        Matrix<double> a, Vector<double> b, IIterativeSolver<double> solver,
        IPreconditioner<double> pre, double tol, bool symmetric) =>
        Try.lift<(IterationStatus Verdict, Vector<double> X)>(() =>
            {
                var x = Vector<double>.Build.Dense(b.Count);
                return (a.TrySolveIterative(b, x, solver, Stack(b.Count, tol, symmetric), pre), x);
            }).Run()
            .Bind(t => Witness.Gate($"verdict={t.Verdict}", Witness.Residual(a, t.X, b), tol).Map(_ => t.X));
}
```

```csharp conceptual
public static class Witness
{
    public static Fin<double> Gate(string evidence, double residual, double cap) =>
        double.IsFinite(residual) && residual <= cap
            ? Fin.Succ(residual)
            : Fin.Fail<double>(Error.New(2200, $"witness failed: {evidence} r={residual}"));

    public static double Residual(Matrix<double> a, Vector<double> x, Vector<double> b) =>
        (b - a.Multiply(x)).L2Norm() / double.Max(b.L2Norm(), double.Epsilon);

    public static double Residual(CompressedColumnStorage<double> a, double[] x, double[] b) {
        var y = new double[b.Length];
        a.Multiply(x, y);
        return TensorPrimitives.Distance<double>(b, y) / double.Max(TensorPrimitives.Norm<double>(b), double.Epsilon);
    }
}
```

## [06]-[SPECTRAL_LAW]

[SYMMETRY_CONTRACT]:
- Law: carry a result `[Union]` with distinct dense-symmetric and dense-general cases; the `Symmetricity` flag selects five output axes together — eigenvector norm, real versus block-diagonal `D`, single-column versus column-pair encoding, ascending versus Schur-deflation order, and a working versus norm-gated solve.
- Law: decode a real conjugate pair from two adjacent columns dispatched on `Math.Sign(values[j].Imaginary)`; reading `Column(j)` whole discards the imaginary half.
- Law: carry `EigenValues` to interpret `EigenVectors`, since no parallel pairing array exists.
- Boundary: census conjugate pairs by counting nonzero `D` super-diagonals — `n − 2·pairs` real eigenvalues — the cheapest spectral-type probe before any eigenvector work.

```csharp conceptual
public static class SchurDecode
{
    public static Matrix<Complex> Modal(Matrix<double> packed, Vector<Complex> values) =>
        Matrix<Complex>.Build.DenseOfColumns(
            Enumerable.Range(0, values.Count).Select(j =>
                Math.Sign(values[j].Imaginary) switch
                {
                    > 0 => packed.Column(j).Enumerate().Zip(packed.Column(j + 1).Enumerate(),
                               (re, im) => new Complex(re, im)),
                    < 0 => packed.Column(j - 1).Enumerate().Zip(packed.Column(j).Enumerate(),
                               (re, im) => new Complex(re, -im)),
                    _   => packed.Column(j).Enumerate().Select(re => new Complex(re, 0.0)),
                }));
}
```

[EIGENVECTOR_QUALITY]:
- Law: `Normalize(2)` each nonsymmetric column before any modal weight; recovered columns are raw triangular solutions with arbitrary per-column norms.
- Law: keep Hermitian eigenvectors complex; projecting them to real parts is incorrect.
- Law: detect a structurally meaningless eigenvector block from the operator norm itself; a zero accumulated Hessenberg-band norm returns the bare similarity transform with valid eigenvalues.
- Boundary: detect defectiveness by a rank or condition probe on `EigenVectors`; a Jordan block never throws and manifests as near-parallel columns.
- Boundary: never assert eigenvalue equality tighter than the convergence band; the exceptional-shift escape bakes the literal `0.964` into the last bits.

[EIGEN_RESIDUAL_AND_FILTER]:
- Law: compute the block defect `(A.Multiply(V) - V.Multiply(D)).FrobeniusNorm()`; no built-in eigen residual exists, and it is the one signal both the managed throw rail and the native in-band info-code rail surface identically.
- Law: retain the full eigenvector matrix from the always-all-`n` dense solve as the cached basis; each filter then pays one `SubMatrix` allocation, never the O(n³) resolve.
- Law: require matching `n` and `Symmetricity` for a basis cache hit.
- Law: own the eigenbasis filter family as a closed weight vocabulary — the eigen-space analog of the Fourier symbol row — excluding the zero mode (`λ < ε_zero ? 0.0 : f(λ)`, excluded never clamped) and carrying the weight sum as evidence so a fully-excluded spectrum fails rather than reads as a zero signal.
- Reject: the library `Determinant`, `Rank`, and `IsFullRank` in domain logic; `Determinant` short-circuits to `0.0` the moment any eigenvalue crosses the absolute zero test.
- Boundary: pin the managed provider once before first provider touch and treat provider identity as a result discriminant; the slot is process-static with no per-call override.
- Boundary: only `DenseMatrix` reaches the native `EigenDecomp`, the managed `Evd` kernels are serial regardless of degree, and sign, ordering, and last bits differ across the seam.

## [07]-[RECEIPT_LAW]

[PROVENANCE_SNAPSHOT]:
- Law: snapshot the provider `ToString` tag, parallelism degree, and the two parallelization thresholds at solve construction; every kernel reads this ambient static at execution instant.
- Law: derive bit-versus-envelope equality from the provider, degree, and threshold triple; the partition-tree topology varies run-to-run, so a recorded value is correct for one core count only and bit-comparison on another host falsely flags tampering.
- Boundary: short-circuit provider-mismatched eigenvector comparison to span equivalence; backends agree only up to sign and span and choose different bases within degenerate eigenspaces.

[HONESTY_MARKERS]:
- Law: store every implicit algorithm choice that shaped a result as a named policy field; a consumer that switch-dispatches on it re-derives behavior and breaks re-admission.
- Law: record `Symmetricity` as the case supplied (the caller's verified precondition), not the library's inferred result; the receipt `IsSymmetric` bool merges `Symmetric` and `Hermitian` and loses the distinction.
- Reject: a `QRMethod.Thin` receipt where full-column-space reconstruction is required.
- Reject: a `computeVectors: false` receipt read for vectors; it leaves `U`/`VT` as identity-shaped stubs.
- Law: assert singular values descending at construction and re-admission, never restoring the order, since a re-sort desyncs every index-0-derived fact.

[ONLINE_STATISTICS]:
- Law: the accumulator is `RunningStatistics` for the whole stream and `MovingStatistics` for a fixed window — distinct semantics recorded as the receipt's accumulator fact, never one knob, since the moving form re-weights as samples leave the window where the running form never forgets.
- Law: carry the Bessel-versus-population normalizer as a policy enum beside every stored deviation, reading `RunningStatistics.Variance`/`StandardDeviation` (`n−1`) versus `PopulationVariance`/`PopulationStandardDeviation` (`n`); unmarked mixing silently corrupts every downstream confidence computation.
- Law: merge partitions through the pure static `RunningStatistics.Combine(a, b)` (the `operator +` form) as a CAS-safe reduction, asserting the identity `combined.Count == a.Count + b.Count`; the parallel accumulation runs to fourth order, so `Skewness`/`PopulationSkewness` and `Kurtosis`/`PopulationKurtosis` survive the merge to the floating-point envelope.
- Boundary: guard the stream at `Push`/`PushRange` admission — one pushed `NaN` permanently poisons `Minimum`/`Maximum` and every moment with no reset — through the same all-finite predicate the operands cross.

[TERMINAL_PARTITION]:
- Law: partition the terminal status as `Converged | StoppedWithoutConvergence | (Diverged | Failure | Cancelled)`; mapping budget-exhausted to `Fin.Fail` destroys the caller's relaxed-criterion or different-preconditioner retry.
- Law: catch the numerical-breakdown child before its non-convergence parent; a parent-first ladder swallows the more specific signal.
- Law: map the singular-`U` index (message-string only) and the zero-pivot sparse status to a distinct singular-matrix domain error, not a blanket solver failure.
- Boundary: only `Expected` errors are wire-faithful with equality by `Code` alone, so convert every exceptional error to a domain-coded expected error before serialization.
- Boundary: `HasCode` dispatch on a round-tripped error is sound where message-substring matching is not.

```csharp conceptual
[Union]
public abstract partial record SolveTerminal
{
    public sealed partial record Admitted(Vector<double> X) : SolveTerminal;
    public sealed partial record Exhausted(Vector<double> Partial, int Budget) : SolveTerminal;
}

public static class Terminal
{
    public static Fin<SolveTerminal> Partition(Fin<(IterationStatus Verdict, Vector<double> X)> run, int budget) =>
        run.Bind(t => t.Verdict switch
        {
            IterationStatus.Converged => Fin.Succ<SolveTerminal>(new SolveTerminal.Admitted(t.X)),
            IterationStatus.StoppedWithoutConvergence => Fin.Succ<SolveTerminal>(new SolveTerminal.Exhausted(t.X, budget)),
            var v => Fin.Fail<SolveTerminal>(Error.New((int)v, $"solver terminal: {v}")),
        })
        .MapFail(e => e switch
        {
            { Exception.Case: NumericalBreakdownException } => Error.New(2201, "numerical breakdown", e),
            { Exception.Case: NonConvergenceException } => Error.New(2202, "iteration non-convergence", e),
            _ => e,
        });
}
```

## [08]-[OWNED_BUILDS]

[QUADRATURE]:
- Law: choose the quadrature route as the accuracy decision, order secondary; double-exponential, fixed Gauss-Legendre, adaptive Gauss-Kronrod, and tensor-product cubature are four distinct kernels, not wrappers.
- Law: admit the integrand as a guarded delegate lifting each evaluation into an absence carrier; no route inspects returns for non-finiteness and a pole poisons the weighted sum silently.
- Boundary: count the skipped evaluation in the receipt, never silently as coverage.
- Boundary: substitute infinite bounds only on the facade entry; the direct double-exponential kernel feeds infinity into abscissa evaluation and yields `NaN` weights.
- Use: the `L1` value-to-ratio cancellation channel as the free conditioning diagnostic; the short overload discards it.
- Boundary: record the terminated-at-budget case with its binding budget and residual; the three exhaustion mechanisms return best-so-far indistinguishable from convergence.

```csharp conceptual
public sealed record QuadratureEvidence(double Value, double Error, double L1Norm, double Ratio, int Skipped);

public static class Quadrature
{
    public static Fin<QuadratureEvidence> Kronrod(Func<double, double> f, double a, double b, double floor)
    {
        var skipped = 0;
        var value = Integrate.GaussKronrod(
            x => f(x) is var y && double.IsFinite(y) ? y : (++skipped, 0.0).Item2,
            a, b, out var error, out var l1Norm);
        return Math.Abs(value / l1Norm) is var ratio && double.IsFinite(ratio) && ratio >= floor
            ? Fin.Succ(new QuadratureEvidence(value, error, l1Norm, ratio, skipped))
            : Fin.Fail<QuadratureEvidence>(Error.New(2301, $"cancellation breach: |value/L1|={ratio} skipped={skipped}"));
    }
}
```

[INTEGRATOR_TABLEAU]:
- Law: validate the tableau at construction; `Create` returns an order-carrying `StepTableau` or a typed structural fault, and row-sum consistency and the order conditions are definition-time facts.
- Law: derive verified order as the largest integer for which every order condition holds, never assert it.
- Law: write one step function over the minimal additive-module operations (addition, scalar scaling, step-scaled increment); it admits scalar, complex, fixed-rank vector, and grid-slab carriers, collapsing the scalar-versus-vector transcription-error class.
- Law: freeze adaptive control as one policy row — safety factor, step-ratio clamps, error-norm choice, and reject budget travel together — and read the next step off the receipt.
- Boundary: use the scaled two-pass error norm for large-magnitude state; the naive squared-sum-then-root overflows, and an infinity in the error channel is then attributable to norm policy.

[SAMPLING]:
- Law: draw stochastic samples seed-explicit over a state-serializable generator for checkpoint-resume; the default thread-entropy source and the length-2048 parallel block fill are non-deterministic regardless of seeding.
- Law: build the low-discrepancy family in the owned lane, since no library surface exists.
- Law: carry the independent-versus-equidistributed discriminant as a type; variance law, error bars, and convergence rate fork on it and the state shapes do not unify.
- Law: accept the block exponent at the draw entrypoint, never a free count; non-power prefixes, dropped origins, and strided thinning degrade discrepancy with no diagnostic, and equidistribution holds only at power-of-base counts.
- Boundary: return a replicate family with cross-replicate variance and a Student bound; a single equidistributed estimate carries no recoverable spread.
- Law: fix the scramble as a variance-law policy row, never a boolean — only the digital-shift randomizer survives progressive extension across exponents.
- Law: carry the net quality parameter and per-coordinate-pair projection figure as structural evidence so gates reject on quality, not on slow convergence.

[SPECTRAL_OPERATOR]:
- Law: collapse every constant-coefficient periodic operator to one symbol applied pointwise to the forward transform; symbols are policy values composed by pointwise multiplication before a single inverse, and a new operator is a new symbol row, never a new code path.
- Law: derive the split-spectrum wavenumber once at grid construction — ascending positives through Nyquist, then descending negatives, scaled by `2π/extent`; hand-indexing the bin number applies an aliased symbol past the half length silently.
- Boundary: fix the asymmetric scaling convention in the owner; the symmetric default cancels only on round trips and is the most common silent error.
- Boundary: zero the Nyquist bin for odd-order symbols.
- Boundary: route B-orthonormalization through `chol.Factor.LU()`; `chol.Factor.Transpose()` yields the silently-wrong half-factor.
- Boundary: mark the result inadmissible on excess imaginary residual; a real-symbol operator owes a machine-zero imaginary part, and excess diagnoses broken Hermitian symmetry.

```csharp conceptual
public readonly record struct WaveAxis(int Length, double Extent)
{
    public double[] K() =>
        Generate.LinearRangeMap(0.0, 1.0, Length - 1.0,
            i => (i < (Length >> 1) + 1 ? i : i - Length) * (2.0 * Math.PI / Extent));

    public int Nyquist => (Length & 1) == 0 ? Length >> 1 : -1;
}

public readonly record struct Symbol(Func<double, Complex> Apply, bool OddOrder)
{
    public static readonly Symbol Laplacian = new(static k => -(k * k), OddOrder: false);
    public static readonly Symbol Gradient = new(static k => Complex.ImaginaryOne * k, OddOrder: true);
    public static readonly Symbol Helmholtz = new(static k => 1.0 / (1.0 + k * k), OddOrder: false);
}

public static class SpectralOperator
{
    public static Complex[] Apply(Complex[] field, WaveAxis axis, Symbol symbol)
    {
        var (k, n) = (axis.K(), axis.Nyquist);
        Fourier.Forward(field, FourierOptions.AsymmetricScaling);
        var driven = field.Select((c, i) => c * (symbol.OddOrder && i == n ? Complex.Zero : symbol.Apply(k[i]))).ToArray();
        Fourier.Inverse(driven, FourierOptions.AsymmetricScaling);
        return driven;
    }
}
```

[INTERPOLANT_AND_SCATTER]:
- Law: lift interpolant capability to a phantom type parameter or marker case so the unsupported call is unrepresentable; the contract advertises differentiation and integration through runtime booleans and throws on unsupported calls.
- Law: reconstruct scattered multi-dimensional fields as a radial-basis or polynomial design matrix into the rank-revealing regression route — no library surface exists, and a matrix-valued response reconstructs gradient and flux fields in one solve.
- Boundary: wrap interpolant evaluation in an absence carrier; the step interpolant returns `NaN` at sample points and the rational interpolant returns `NaN` below ULP, poisoning a gradient accumulator silently.
- Use: the serial kernel-density route for reproducibility; it parallelizes uncapped and is non-reproducible across schedules even when seeded.
