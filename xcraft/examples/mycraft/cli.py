import sys

import click


@click.group()
@click.option("--debug", is_flag=True, default=False)
@click.option("--enable-developer-debug", is_flag=True, default=False)
@click.option("--shell", is_flag=True, default=False)
@click.pass_context
def main(ctx, debug, enable_developer_debug, shell) -> int:
    print("cli: snapcraft")
    ctx.ensure_object(dict)
    ctx.obj["MYCRAFT_DEBUG"] = debug
    ctx.obj["MYCRAFT_ENABLE_DEVELOPER_DEBUG"] = enable_developer_debug
    ctx.obj["MYCRAFT_SHELL"] = shell
    print(f"cli: {ctx.obj!r}")
    return 0


@main.command("build")
@click.argument("parts", nargs=-1, metavar="<part>...", required=False)
@click.pass_context
def build(ctx, parts) -> int:
    ctx.obj["MYCRAFT_COMMAND"] = ["build", *parts]
    print(f"cli: {ctx.obj!r}")

    return 0


@main.command("magic")
@click.pass_context
def magic(ctx) -> int:
    ctx.obj["MYCRAFT_COMMAND"] = ["snap"]
    print(f"cli: {ctx.obj!r}")
    return 0


if __name__ == "__main__":
    sys.exit(main())  # pragma: no cover
