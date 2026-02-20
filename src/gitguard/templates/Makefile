release-%:
	hatch version $*
	git add {version_path}
	git commit -m "chore: release $$(hatch version)"
	git push
