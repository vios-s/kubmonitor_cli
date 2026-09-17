# Workload Ownership Labels

kubmonitor identifies who owns each workload in a shared namespace by
reading Kubernetes labels. Job generators (e.g. a group's template repo)
should stamp these on **both** the Job's `metadata.labels` and the pod
`spec.template.metadata.labels`.

## Labels

| Label | Required | Example | Meaning |
|---|---|---|---|
| `owner` | **yes** | `rasin` | The cluster account that owns this workload (login account name, not a display name). |
| `project` | **yes** | `mri_recon` | The *research* project this workload is work on — the strand of work it belongs to, chosen by the owner. |
| `purpose` | recommended | `batch` | One of `batch`, `interactive`, `serving`. |

### `project` is your research project, not your allocation code

The point of `project` is to separate one person's strands of work:
`mri_recon`, `fairness`, `diffusion_priors`. Two people on the same
research project use the same value; one person running three projects
uses three.

Do **not** put the compute allocation / group code (`eidf105`) here. Every
workload in a namespace belongs to the same allocation, so that value is
identical on every row and distinguishes nothing. It is also already
recorded — it is what the namespace *is*, and kubmonitor stores the
namespace alongside every workload.

Pick something short, stable and reusable across runs. Reports group by
this value verbatim, so `mri_recon` on Monday and `mri_recon_v2` on Tuesday
are two different projects.

Label *values* may contain letters, digits, `-`, `_` and `.` (max 63
chars), so accounts like `ada_lovelace` are valid values — note that
underscores are **not** valid in resource *names*, which is why labels
beat name conventions for identifying owners.

**Separator convention: underscores.** `mri_recon`, not `mri-recon`. Both
are legal label values, which is exactly the problem — pick one or reports
end up with each project split across two spellings. This group follows
its account names (`ada_lovelace`).

To make that convention enforceable rather than aspirational, a project
config may list the group's known projects:

```yaml
research_projects: [mri_recon, fairness, diffusion_priors]
```

`kubmonitor validate` then warns about a value that is not listed, and
when the value differs from a listed one only by separator or case it says
so outright:

```
warning: job.yaml: Job project 'mri-recon' is not registered, but
'mri_recon' is — same name, different spelling? Reports count them
separately
```

It is a **warning, never an error**: someone starting a new project at
2am must not have to land a config change before they can submit a job.
Leave the key out to switch the check off.

A custom prefix (e.g. `example.org/owner`) is supported via the
`label_prefix` project-config option and `kubmonitor validate --prefix`;
the default contract is unprefixed.

## Example

```yaml
apiVersion: batch/v1
kind: Job
metadata:
  generateName: cuda-rasin-
  labels:
    kueue.x-k8s.io/queue-name: eidf105ns-user-queue
    owner: rasin
    project: mri_recon
    purpose: batch
spec:
  template:
    metadata:
      labels:
        app: cuda
        owner: rasin
        project: mri_recon
        purpose: batch
    spec:
      ...
```

## How kubmonitor resolves the owner

1. `owner` label (workload's own labels, then its pod template's);
2. name matching: a `-`-separated token of the Job/Pod name equal to a
   known account — or a declared `aliases:` nickname — from the project's
   members file (underscores in account names are compared against `-`
   in names);
3. image matching: the Docker-Hub-style account segment or the image tag,
   but only when it matches a declared account/alias from the members
   file — an arbitrary image name is never trusted on its own;
4. otherwise the workload is listed separately as *unattributed*, never
   silently dropped.

The resolved *account* maps to a *person* via the members file
(`examples/members.yaml`), so one person with several accounts appears
as a single row in reports.

## Existing usage data

The `project` label was required by `kubmonitor validate` from the start,
but the collector never read it, so **no historical value exists to
migrate**. Nothing needs to be rewritten, and nothing is lost.

Opening the DB adds a `workloads.research_project` column automatically
(`usagedb._migrate`); this is additive and safe to run against a live DB
with a cron collector writing to it. Workloads collected before the upgrade
keep `NULL` there, and so do workloads that carry no `project` label.

`NULL` means *unknown*, and must not be backfilled to `eidf105`: the old
label said only "this workload is in the eidf105 allocation", which is not
a research project and is already implied by the namespace. Any report
grouping by this column should show unknowns as their own bucket rather
than folding them into a real project. Expect every pre-upgrade row to sit
in that bucket — a per-project breakdown only becomes meaningful for
workloads submitted after the templates start filling the label.

## Two things called "project"

Confusingly, `project` currently names two unrelated things:

| Where | Means | Example |
|---|---|---|
| the `project` **label** (this document) | the owner's research project | `mri_recon` |
| the `project:` key in a kubmonitor **project config** | which namespace this config monitors, and the scope key for its rows in the DB | `eidf105` |

For a single-namespace setup the config key is redundant — it is the
namespace with `ns` stripped, and `namespace:` sits right beside it. It is
not, however, merely a duplicate: two configs sharing a `project` id but
naming different namespaces, and writing to one DB, produce a report
aggregated across both. Nothing does that today, so collapsing the two is
worth considering — but only alongside work that touches the report
queries anyway, not as a standalone migration of a live DB.

Until then, read the word by its location: in a manifest it is the
research project, in `project.yaml` it is the allocation.

kubmonitor records the label on each workload as `research_project`, kept
verbatim; the DB column is spelled differently only to avoid colliding with
the legacy scope column.

## Checking a manifest

```bash
kubmonitor validate path/to/job.yaml
```

exits non-zero and prints what's missing if the manifest lacks the
required labels (or still contains unfilled `<PLACEHOLDER>`s).
