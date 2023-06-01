#!/usr/bin/env python3
from rhnode import RHJob
import argparse


def main():
    # Create top-level parser
    parser = argparse.ArgumentParser(prog="rhrun")
    parser.add_argument(
        "-o", "--output_directory", default=None, help="Output directory [default: .]"
    )
    parser.add_argument(
        "-ma",
        "--manager_address",
        type=str,
        default=None,
        help="Manager address in the form host:port [mutually exclusive with --node_address]",
    )
    parser.add_argument(
        "-na",
        "--node_address",
        type=str,
        default=None,
        help="Node address in the form host:port [mutually exclusive with --manager_address]",
    )
    parser.add_argument(
        "-p", "--priority", type=int, default=3, help="Priority of the job [1-5]"
    )
    parser.add_argument(
        "-nc",
        "--no_cache",
        action="store_true",
        help="The node will run the job even if the result is in the cache",
    )
    parser.add_argument(
        "-ns",
        "--no_save_cache",
        action="store_true",
        help="The node will not save the output files in the cache",
    )
    parser.add_argument(
        "-r", "--resources_included", action="store_true", help="help for arg1"
    )
    parser.add_argument("-g", "--gpu", type=int, default=None, help="help for arg1")
    parser.add_argument("node_name", help="The identifier for the task")
    parser.add_argument(
        "node_args",
        nargs=argparse.REMAINDER,
        help="The arguments for the job in the form arg1=val1 arg2=val2. Run 'rhjob [args] [node_name] -h' for help on the input and output fields of the node",
    )

    args = parser.parse_args()

    print(args.node_args)

    print(f"Task identifier: {args.node_name}")

    job = RHJob(
        node_name=args.node_name,
        inputs=args.node_args,
        manager_address=args.manager_address,
        node_address=args.node_address,
        output_directory=args.output_directory,
        check_cache=not args.no_cache,
        save_to_cache=not args.no_save_cache,
        resources_included=args.resources_included,
        priority=args.priority,
        included_cuda_device=args.gpu,
        _cli_mode=True,
    )

    if len(args.node_args) == 1 and args.node_args[0] in ["-h", "--help"]:
        job.print_cli_help()
    else:
        job.start()
        job.wait_for_finish()


if __name__ == "__main__":
    main()
