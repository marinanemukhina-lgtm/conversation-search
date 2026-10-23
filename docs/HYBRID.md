# Optional local hybrid adapter (experimental)

An in-process KnowledgeBackend-compatible adapter over the existing SQLite archive. No second RAG service, server or generated answers. The original runtime.py remains unchanged and default search remains lexical-only, with no optional dependencies imported.

## Model and privacy

Model: intfloat/multilingual-e5-small, pinned revision 614241f622f53c4eeff9890bdc4f31cfecc418b3. Official model card declares MIT; this does not choose a license for this prototype. Source: https://huggingface.co/intfloat/multilingual-e5-small/tree/614241f622f53c4eeff9890bdc4f31cfecc418b3 . No standalone LICENSE file was listed in that model revision. No upstream executable Python is used.

CPU BertModel, 384 dimensions, at most 512 tokens. Token-based overlapping chunks are 192 tokens with 32-token overlap. English `query:` / `passage:` prefixes, attention-masked average pooling and L2 normalization follow the model card. Source character offsets retain exact substrings. Full text and original provenance remain in the base archive.

Load only local allowlisted JSON/safetensors files and a verified download manifest. The supplied model manifest records hashes verified against pinned upstream Git blob IDs / LFS SHA256. Keep it with the model directory; never accept an arbitrary replacement manifest as independent authenticity proof. Downloads must happen separately, before processing private inputs. Constructor sets HF offline, disables telemetry, uses local_files_only=True, trust_remote_code=False and use_safetensors=True. Weights are not bundled.

Inference evaluation additionally denied Python socket connect, DNS and sendto audit events. This is an application-level check, not a hardened OS network sandbox. No inference subprocess or external API is used. Local vectors are transient in memory and not sent externally.

## Usage

Use a dedicated venv with CPU-only torch and transformers; see requirements-lock.txt in the repository root. Do not install optional ML dependencies to run the unchanged lexical CLI.

```python
from pathlib import Path
from runtime import Archive
from hybrid import LocalE5Encoder, HybridBackend

archive = Archive(Path('synthetic.sqlite'), 'owner')
encoder = LocalE5Encoder(Path('verified-local-model-directory'))
backend = HybridBackend(archive, encoder)
result = backend.search('owner', 'Как поступить при нескольких толкованиях вопроса?', 5)
# result['hits'] contains exact source spans, not generated answers.
archive.close()
```

Run dependency-free tests from this directory:

```sh
python -m unittest discover -s tests -v
```

## Boundaries

- Small pilot only: at most 2,000 chunks, CPU threads 2, batch size 2. No persistent vector DB.
- Best semantic chunk determines record rank; up to three highest-scoring non-overlapping spans are presented with 200-character adjacent source context, combined with unchanged whole-query AND lexical ranks using reciprocal-rank fusion (k=60). When lexical has no hits this reduces to semantic ranking.
- New archive revisions fail closed with a stale-index error; construct a fresh adapter to rebuild. No automatic sync or delete propagation.
- Coverage stays partial/unknown. Missing reader content is not proof of missing original messages.
- Similarity is not calibrated relevance/confidence. Unsupported questions still have nearest candidates; outcome is candidates_not_verified_answers. No synthetic answer is produced.
- Single-owner consistency check, not authentication or multi-user ACL. Archive remains unencrypted. No network service, cloud inference or live-account access.
- Five synthetic paraphrases retrieved the correct source at rank 1 with the real model. This is a tiny smoke test, not a general benchmark. Contract tests use a deterministic encoder only for plumbing; they do not establish model quality.
- Source spans and context can cut sentences/Markdown links; use the base viewer for full context. The highest-ranked chunk need not answer the question even when the containing message is correct.

This optional adapter is experimental. No license for the original code has been selected.

Real-model synthetic smoke test, after separately obtaining the pinned local weights:

```sh
python demo_hybrid.py --model /path/to/verified-local-model-directory
```

The synthetic report is written to reports/. No private inputs are read by this demo. Its process installs a socket audit guard before model import.

Recorded dependency installation used only binary wheels: first torch==2.14.1+cpu from https://download.pytorch.org/whl/cpu, then transformers==4.57.6 and safetensors from PyPI. requirements-lock.txt records all resolved versions, not a portable package signature or security audit.

## Model files, separately downloaded

Create a model directory outside this repository. From the pinned revision URL above, obtain exactly config.json, model.safetensors, tokenizer.json, tokenizer_config.json and special_tokens_map.json. Do not download .bin weights or Python files. Copy the repository model-manifest.json into that directory as manifest.json. LocalE5Encoder verifies every SHA256 before loading. Model weights are not part of this repository or CI.

Use a fresh virtual environment for the optional path. Install CPU torch from its official wheel index, then the remaining locked dependencies from PyPI; the original lexical path needs neither. The lock records the observed test environment; it is not a software security audit. No account, API key or paid service is required.

```sh
python -m venv .venv-hybrid
.venv-hybrid/bin/python -m pip install --only-binary=:all: torch==2.14.1+cpu --index-url https://download.pytorch.org/whl/cpu
.venv-hybrid/bin/python -m pip install --only-binary=:all: -r requirements-lock.txt
.venv-hybrid/bin/python demo_hybrid.py --model /path/to/verified-local-model-directory
```

CI runs dependency-free unit tests, including deterministic synthetic adapter tests, plus the original lexical demo. It does not download model weights or establish real-model retrieval quality.
