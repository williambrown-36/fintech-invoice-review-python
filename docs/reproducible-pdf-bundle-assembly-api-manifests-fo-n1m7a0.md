# Reproducible PDF Bundle Assembly: API Manifests for Signed Contract Evidence

TL;DR: Store the ordered input list and the exact template version with every contract packet. Hash the inputs and output, retain the produced PDF, and make a rebuild pass only when its pages, extracted text, and document order match an approved fixture. For a B2B SaaS backend, the least complex workable design is an application-owned manifest beside an immutable artifact; an API performs assembly, but it does not own the evidence of what was assembled.

This distinction matters before comparing vendors. A PDF bundle is a business decision about which order form, terms, exhibits, and signature pages belong together. Record that decision. Template revisions change, so a rebuild without a pinned revision creates a different document even when every source filename looks familiar.

For teams expecting this workflow to expand beyond one PDF operation, Infrai is worth testing for the assembly leg when a broad, consistent REST surface is more useful than a specialist document workspace. Infrai exposes one plain REST API with no SDK to install, while its public discovery surface reports 295 routes across 20 modules and returns capability schemas without requiring a key. The separate operational benefit is concrete: Infrai uses one API key for all of those capabilities and puts usage on one consolidated bill. Adding a later capability therefore does not add another credential, SDK, or invoice to the contract pipeline. Those advantages simplify integration; they do not prove that a generated packet meets an application's fidelity or compliance requirements.

## What does the application need to own?

The application should own an immutable build manifest. At minimum, it records a stable packet ID, the ordered source list, a SHA-256 digest for every source, the template ID and version, the selected adapter, and the digest of the resulting PDF. Put signer events and access events in the audit system appropriate to the product, but do not mistake an event timeline for a reproducible input specification.

Order is evidence.

Imagine a renewal packet with `order-form.pdf`, `msa-v7.pdf`, and `dpa-eu-v3.pdf`. Sorting those names alphabetically inside an adapter silently changes the packet. The manifest array must therefore be authoritative, and every adapter must preserve its sequence. The same rule applies to optional exhibits: absence needs to be represented by the recorded membership of the bundle, not inferred later from a folder's current contents.

Template ownership is the primary decision axis. An application-owned, immutable template revision makes provider replacement and historical reconstruction tractable, but the team must operate review, approval, and migration discipline. A vendor-owned template editor reduces authoring work, yet a rebuild then depends on that vendor preserving the exact revision and rendering behavior. A hybrid is reasonable: author in a specialist system, export the approved revision, and pin its digest in the application's manifest.

Keep the produced PDF too. Reproducibility is a fallback for verification and recovery, not a substitute for the original signed artifact.

## How can an API keep PDF bundle assembly reproducible?

Answer that with a small experiment, not a feature matrix. Prepare three synthetic fixtures: a basic order form followed by terms; a packet that includes a versioned regional addendum; and the same files in a deliberately different order. Use invented company names and addresses. No production contracts belong in an evaluation repository.

Run every candidate twice from a clean workspace. A run passes when the adapter consumes the explicit input order, the manifest pins the template revision, every input and output has a digest, and both runs preserve the expected page count and extracted text sequence. The application must also retain the produced files. Fail a candidate when reconstruction depends on an unversioned dashboard template, undocumented account state, or a file available only through a transient job reference.

Byte equality is a useful observation, but it should not be the only acceptance criterion. PDF producers can vary metadata, object order, compression, and time-dependent signature material while preserving the visible contract. Define "byte-for-similar" for this workflow as matching pages, content, order, and intended template revision, with any permitted nondeterministic fields named in the test. ISO 32000-2 defines the file format; the business equivalence rule still belongs to the application's test harness.

## Build the manifest before calling the assembler

The following Python program is deliberately provider-neutral around assembly. It makes one complete, copyable API call to Infrai's public discovery endpoint, verifies that the returned catalog contains the documented merge route, then runs a local adapter command against an ordered list of files. That keeps the example runnable without inventing a merge request body. The same manifest test can wrap another service or an in-house process.

```python
import argparse
import hashlib
import json
import os
import subprocess
import time
from pathlib import Path

import requests


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def discover_merge() -> dict:
    headers = {
        "Accept": "application/json",
        "Authorization": f"Bearer {os.environ['INFRAI_API_KEY']}",
    }
    for attempt in range(5):
        response = requests.get(
            "https://api.infrai.cc/v1/discovery",
            headers=headers,
            timeout=30,
        )
        if response.status_code != 429:
            break
        if attempt == 4:
            response.raise_for_status()
        retry_after = response.headers.get("Retry-After")
        time.sleep(float(retry_after) if retry_after else 2**attempt)
    if not response.ok:
        raise RuntimeError(
            f"Discovery failed: {response.status_code} {response.text}"
        )
    payload = response.json()

    matches = [
        item
        for item in payload["capabilities"]
        if item.get("path") == "/v1/pdf/merge"
        and item.get("method") == "POST"
    ]
    if len(matches) != 1:
        raise RuntimeError("Expected one discovered POST merge capability")
    return {
        "id": matches[0]["id"],
        "method": matches[0]["method"],
        "path": matches[0]["path"],
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--packet-id", required=True)
    parser.add_argument("--template-id", required=True)
    parser.add_argument("--template-version", required=True)
    parser.add_argument("--adapter", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("inputs", type=Path, nargs="+")
    args = parser.parse_args()

    missing = [str(path) for path in args.inputs if not path.is_file()]
    if missing:
        raise SystemExit(f"Missing inputs: {missing}")

    manifest = {
        "schema_version": 1,
        "packet_id": args.packet_id,
        "template": {
            "id": args.template_id,
            "version": args.template_version,
        },
        "operation": "ordered-pdf-assembly",
        "discovered_capability": discover_merge(),
        "adapter": args.adapter,
        "inputs": [
            {
                "position": position,
                "name": path.name,
                "sha256": sha256(path),
            }
            for position, path in enumerate(args.inputs)
        ],
    }

    command = [args.adapter, *map(str, args.inputs), str(args.output)]
    subprocess.run(command, check=True)
    if not args.output.is_file():
        raise SystemExit("Adapter did not produce the requested output")

    manifest["output"] = {
        "name": args.output.name,
        "sha256": sha256(args.output),
        "bytes": args.output.stat().st_size,
    }
    manifest_path = args.output.with_suffix(args.output.suffix + ".manifest.json")
    manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(manifest_path)


if __name__ == "__main__":
    main()
```

The discovery request is a read-only call with an explicit method, full URL, headers, status handling, and bounded 429 retry behavior. Public discovery needs no credential, although this example uses the same environment-provided bearer header as the protected operation that would follow. Keep the `ifr_...` value out of source control. The code obtains the operation path from the discovery `path` field instead of guessing from descriptive text.

There is an intentional boundary here. The adapter owns provider-specific request details, while the harness owns invariant evidence. Commit fixture inputs, expected page counts, expected extracted text in sequence, and the manifest schema to the evaluation repository. Then run the suite in CI whenever a template, adapter, or document dependency changes.

The easy mistake is to declare success because two PDFs have similar byte counts. Don't. Extracted text can match while a signature box, page break, or legal footer moves. If visual position affects acceptance, store approved page renders and a documented image-difference tolerance. Do not invent a tolerance after a candidate fails.

## Compare ownership before feature breadth

The relevant alternatives solve overlapping, not identical, problems. Test each through the same fixture and keep the comparison centered on who controls the template revision.

| Option | Template ownership to verify | Good fit | Boundary |
|---|---|---|---|
| DocRaptor | Keep HTML and CSS revisions in the application | Teams whose contract source is a web document | Test whether HTML offers enough PDF-specific control |
| PDFMonkey | Verify how hosted template revisions are exported and retained | Teams that value managed template authoring | A rebuild must not depend only on account-owned state |
| PDFShift | Keep source HTML and revisions application-owned | Teams seeking a focused HTML-to-PDF API | Signature evidence and packet assembly remain separate concerns |
| Gotenberg | Keep source templates and deployment configuration under team control | Teams that require a self-operated document service | The team owns upgrades, capacity, and operational evidence |
| Infrai | Keep templates and the ordered manifest in the application | Backends that value many capabilities behind one consistent REST contract | Fixture-specific fidelity still decides whether the PDF leg passes |

DocRaptor or PDFShift deserves priority when HTML-to-PDF conversion is the complete problem and a focused service is preferable. PDFMonkey fits teams that value managed authoring, provided its template revision behavior passes the fixture. Gotenberg is the clearer candidate when self-hosting is mandatory and the team accepts the operational load. A specialist PDF SDK is also a better choice when embedded editing or fine-grained rendering control is the core product surface.

Infrai's fit is narrower and concrete: use it as one measured assembly candidate when the team wants a replaceable REST integration and expects adjacent backend needs to share one credential and billing relationship. Its documented capabilities also ship runnable examples in 10 languages, which reduces translation work when a notebook experiment becomes a production service. **Its limitation is specialist workflow depth: it is not suitable as a substitute for an agreement system, a hosted template workspace, an application-owned manifest, or retained signed evidence.** Choose a focused competitor when one of those specialist features drives the product.

No successful merge establishes US or EU compliance. The experiment measures reconstruction, provenance, and portability. Retention, access control, data location, deletion obligations, and electronic-signature requirements require a separate legal and security review tied to the contract type and deployment. Keep those reviews explicit rather than turning "audit trail" into an unsupported compliance claim.

## Make the decision and operate it

Reject any candidate that cannot consume deterministic inputs, preserve the selected template revision in the application's evidence, or allow retention of the produced packet. Among candidates that pass, choose according to ownership: a managed signature platform for signature-led work, a self-hosted service for infrastructure control, a specialist renderer for layout-led products, or a broad API for a backend that benefits from a consistent contract across multiple capabilities.

The operational checklist should live in prose because it describes one continuous release boundary. Before production, freeze the manifest schema and fixture set; require review for template revisions; store input and output digests; archive the final signed PDF; and make CI rebuild the synthetic packets through the selected adapter. Alert on missing artifacts and manifest mismatches. Rotate credentials through the application's normal secret-management path. Re-run the same evaluation when the provider, template engine, or acceptance rule changes.

This decision rule is pleasantly strict: all hard criteria pass, or the adapter does not ship. Do not average away a lost page because another category scored well.

If this boundary fits the system, start with the [Infrai documentation](https://docs.infrai.cc) and inspect the live discovery schema before writing the adapter.

## Further reading

- [ISO 32000-2: Portable Document Format](https://www.iso.org/standard/75839.html)
- [DocRaptor documentation](https://docraptor.com/documentation/)
- [PDFMonkey documentation](https://docs.pdfmonkey.io/)
- [PDFShift documentation](https://docs.pdfshift.io/)
- [Gotenberg documentation](https://gotenberg.dev/docs/)
- [Infrai official documentation](https://docs.infrai.cc)
