# Module: src/cli/

| File | Role |
|------|------|
| [ArgumentParser.cpp](../../src/cli/ArgumentParser.cpp) | positional + flag parsing |
| [ConsoleOutput.cpp](../../src/cli/ConsoleOutput.cpp) | colored console messaging (WARNING/ERROR/INFO) |

## Dispatch

`main()` in [main.cpp](../../src/main.cpp) selects the subcommand by `argv[1]`. Per-command
entry points (`runXxx`) live in [[modules/commands#Module: src/commands/]].

TODO: log levels, env-var overrides, color/no-color flag.
