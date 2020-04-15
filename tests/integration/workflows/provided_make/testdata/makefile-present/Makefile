build-HelloWorldFunction:
	cp -r *.py $(ARTIFACTS_DIR)
	cp -r requirements-requests.txt $(ARTIFACTS_DIR)
	python -m pip install -r requirements-requests.txt -t $(ARTIFACTS_DIR)
	rm -rf $(ARTIFACTS_DIR)/bin
