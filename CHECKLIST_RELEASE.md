# Release Checklist

External steps for the user after the local reproduction package is ready:

1. Initialize git, make the first commit, and create a release tag such as `v1.0.0`.
2. Create the GitHub repository and push the tag and main branch. The CI workflow in `.github/workflows/reproduce.yml` runs automatically on push and pull request.
3. Upload the deposit to Zenodo using the existing `.zenodo.json` metadata and obtain the DOI.
4. Add the DOI to `.zenodo.json`, `CITATION.cff`, and the manuscript.

Steps 3 and 4 are manuscript-closing tasks and remain deferred, matching the paper-4 release boundary.
