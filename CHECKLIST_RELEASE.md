# Release Checklist

The remaining external release steps are:

1. Merge `derisk-fakebackend-prereg` into `main` and push the merge.
2. Create and push tag `v1.1.0`; the minor-version increment records the additive
   robustness studies and hardware archive now reported by the package.
3. Confirm that every GitHub Actions job is green for the tagged commit.
4. Create the Zenodo deposit from that release and obtain its version-specific DOI.
5. Add the DOI and release tag to `.zenodo.json`, `CITATION.cff`, and the
   manuscript's Code and data availability statement.

Do not mint or insert a provisional DOI before the tagged release artifact exists.
