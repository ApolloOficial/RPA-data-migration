.PHONY: build-MigrationFunction

build-MigrationFunction:
	mkdir -p "$(ARTIFACTS_DIR)/app"
	cp app/*.py "$(ARTIFACTS_DIR)/app/"
	python3 -m pip install --only-binary=:all: --platform manylinux2014_x86_64 --implementation cp --python-version 3.12 --target "$(ARTIFACTS_DIR)" -r requirements.txt
