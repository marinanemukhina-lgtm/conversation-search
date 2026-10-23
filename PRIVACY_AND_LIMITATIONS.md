# Privacy and limitations

No real conversations, source links, personal identifiers, credentials or private reports are included. Fixtures and test provenance are synthetic. No outbound network, model calls, OAuth grants or ongoing access are created by this code.

Local SQLite stores original bytes and normalized text unencrypted. Local OS users with access can read them. --owner is a consistency guard, not authentication. This is not a multi-user server. Operators must control file permissions and backups; .gitignore is only an accident guard, not a privacy boundary.

Coverage is partial or unknown, never complete. Missing results mean no match in the imported scope. Omitted content is not indexed and does not imply the source conversation lacks that content. Search uses literal Unicode tokens with AND and BM25; no semantic similarity, stemming, typo correction, automatic question rewriting or synthesis.

Context order is first-observed order, not attested source chronology. Revisions are observations; a previously unseen old snapshot may appear new. WhatsApp identities are heuristic (date/author/occurrence). No deletion propagation, revocation, purge workflow, media OCR/ASR, live sync or complete service-history guarantee.

Limits: 8 MiB per file/member, 24 MiB bundle and expanded aggregate, 100 ZIP members, compression ratio at most 100, 10,000 records/file, 100,000 characters/message, 100 search hits. Only one WhatsApp date/locale profile is supported. HTML-only EML is rejected. No linked pages or attachments are fetched.

The larger architecture in docs is planned, not implemented. Product evaluation, security audit, real-export compatibility and license choice remain separate requirements.
