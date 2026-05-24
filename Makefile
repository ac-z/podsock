# Podsock - podman wrapper with +flags.
# Copyright (C) 2026 Amber Connelly
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

PREFIX ?= $(HOME)/.local
DESTDIR ?=
BINDIR = $(PREFIX)/bin
COMPLETIONDIR = $(PREFIX)/share/bash-completion/completions
ALIAS ?=

.PHONY: install uninstall completions test

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

test:
	@which pytest > /dev/null 2>&1 || { echo "pytest is required to run tests. Install it (e.g. apt install python3-pytest) and try again."; exit 1; }
	@pytest test_podsock.py -v
