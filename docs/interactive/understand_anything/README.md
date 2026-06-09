# Understand-Anything Published Graph Asset

This folder is reserved for reviewed Understand-Anything graph assets used by the static Interactive Project Explorer.

- Raw local output lives under `.understand-anything/`.
- The static docs viewer loads a reviewed asset from this folder when available.
- Do not commit intermediate cache, secrets, local credentials, Terraform state, `.tfvars`, `.env` files, or unreviewed local artifacts.
- Regenerate locally with `/understand --language en`.
- Review the generated graph before publishing it here.

Preferred published asset names:

- `knowledge-graph.public.json` for reduced/sanitized graph output.
- `knowledge-graph.json` only when the raw graph is small, reviewed, and safe to publish.

