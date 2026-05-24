PREFIX ?= $(HOME)/.local
DESTDIR ?=
BINDIR = $(PREFIX)/bin
COMPLETIONDIR = $(PREFIX)/share/bash-completion/completions
ALIAS ?=

.PHONY: install uninstall completions

install: podsock.py
	@echo "Installing podsock to $(DESTDIR)$(BINDIR)"
	@mkdir -p $(DESTDIR)$(BINDIR)
	@install -m 755 podsock.py $(DESTDIR)$(BINDIR)/podsock
	@$(MAKE) completions
	@echo "Installation complete. podsock is now in $(DESTDIR)$(BINDIR)/podsock"

uninstall:
	@echo "Removing podsock from $(BINDIR)"
	@rm -f $(DESTDIR)$(BINDIR)/podsock
	@echo "Removing completions from $(COMPLETIONDIR)"
	@rm -f $(DESTDIR)$(COMPLETIONDIR)/podsock
	@if [ -n "$(ALIAS)" ]; then \
		echo "Removing completion alias $(ALIAS)"; \
		rm -f $(DESTDIR)$(COMPLETIONDIR)/$(ALIAS); \
	fi
	@echo "Uninstall complete"

completions: podsock.py
	@echo "Installing bash completions to $(DESTDIR)$(COMPLETIONDIR)"
	@mkdir -p $(DESTDIR)$(COMPLETIONDIR)
	@python3 podsock.py --bash-completion > $(DESTDIR)$(COMPLETIONDIR)/podsock
	@if [ -n "$(ALIAS)" ]; then \
		echo "Creating completion alias: $(ALIAS) -> podsock"; \
		ln -sf podsock $(DESTDIR)$(COMPLETIONDIR)/$(ALIAS); \
	fi
