"""Agentoo CLI policy — read before adding or changing command surface.

Normal commands are Python agentoo-NAME executables. The dispatcher only routes;
each command owns one parser, validation, privileges, help, and completion.
Checkpoint is independently runnable POSIX sh, with no Python dependency.
Use readable GNU long options, familiar short names, --help, and --. Disable
implicit option abbreviations. Validate before privileges or effects; requested
help succeeds without either. Results and explicit help go to stdout; plans,
progress, warnings, and operational summaries go to stderr. Argument errors
print the diagnostic followed by contextual help to stderr and exit 2. Document
stable machine output and exit semantics where useful. Commands supporting --no-input
must never prompt, including for privileges or authentication. Respect XDG,
redirection, terminal capabilities, and NO_COLOR where applicable. Prefer
additive changes and document deliberate exceptions. New surface requires
implementation, help/completion, policy exceptions, and focused verification
together. Tests cannot discover every undeclared behavior.

Keep helpers small and based on actual repetition: no command framework,
metadata schema, plugin discovery, or mandatory options without a use case.
"""
import argparse
import sys


class ArgumentParser(argparse.ArgumentParser):
    def __init__(self, *args, **kwargs):
        kwargs.setdefault('allow_abbrev', False)
        super().__init__(*args, **kwargs)

    def error(self, message):
        parser = getattr(self, '_help_parser', self)
        print(f'{parser.prog}: error: {message}\n', file=sys.stderr)
        parser.print_help(file=sys.stderr)
        self.exit(2)

    def parse_args(self, args=None, namespace=None):
        # Explicit help wins over incomplete arguments, but never inspect data
        # following --. Walk known subparsers without running validation/actions.
        tokens = list(sys.argv[1:] if args is None else args)
        before_boundary = tokens[:tokens.index('--')] if '--' in tokens else tokens
        parser = self
        pending = False
        for token in before_boundary:
            if token in ('-h', '--help'):
                break
            if pending:
                pending = False
                continue
            option = parser._option_string_actions.get(token.split('=', 1)[0])
            if option is not None:
                pending = option.nargs != 0 and '=' not in token
                continue
            for action in parser._actions:
                if isinstance(action, argparse._SubParsersAction) and token in action.choices:
                    parser = action.choices[token]
                    break
        # argparse reports leftover unknown options at the root parser; retain
        # the selected command so those errors show its help instead.
        self._help_parser = parser
        if any(token in ('-h', '--help') for token in before_boundary):
            parser.print_help()
            self.exit(0)
        return super().parse_args(tokens, namespace)
