#!/usr/bin/env python3
"""Generate a Cardano MAINNET wallet for anchoring — REAL key, REAL ADA.

DANGER — READ BEFORE RUNNING
    This generates a REAL mainnet signing key that will control REAL ADA.
    The 64-hex seed inside the written .skey file is the ENTIRE secret:
    anyone holding those 64 hex characters holds the wallet.

    Operator ceremony (in this order, BEFORE funding):
      1. Run this script once. It writes the key file and prints ONLY the
         mainnet address (addr1...). Pin that address as
         GRANTLAYER_CARDANO_EXPECTED_ADDRESS.
      2. Hand-copy the 64 hex chars after "5820" from the key file to paper
         (your own offline act — this script never displays them).
      3. Prove the paper copy: run --verify-backup and type the hex back from
         the PAPER, not the file. MATCH against the pinned address means the
         backup is good. Only then fund the wallet (25 ADA cap).
      4. NEVER run the generation twice: the output is opened with O_EXCL and
         the script hard-fails if the key file already exists. Do not delete
         the file to "retry" — a funded key that is lost is ADA that is lost.

    This script only ever writes secrets/cardano_signing_key_mainnet. It is
    structurally incapable of touching the preprod key file.
"""
import argparse
import getpass
import json
import os
import stat
import sys

# pycardano 0.19.2 refuses to import without this; set before the first import.
os.environ.setdefault("CBOR_C_EXTENSION", "1")

from pycardano import (
    Address,
    Network,
    PaymentSigningKey,
    PaymentVerificationKey,
)

KEY_PATH = "secrets/cardano_signing_key_mainnet"

# The .skey envelope is boilerplate around the seed: these two fields are
# constants, and cborHex is "5820" (CBOR: 32-byte string) + the 64-hex seed.
KEY_TYPE = "PaymentSigningKeyShelley_ed25519"
CBOR_PREFIX = "5820"


def derive_mainnet_address(sk: PaymentSigningKey) -> str:
    vk = PaymentVerificationKey.from_signing_key(sk)
    return str(Address(vk.hash(), network=Network.MAINNET))


def generate() -> int:
    # 1. Refuse to overwrite: O_EXCL makes a second run a hard error. This is
    #    the structural guard against destroying a (possibly funded) key.
    try:
        fd = os.open(KEY_PATH, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError:
        print(
            f"REFUSED: {KEY_PATH} already exists.\n"
            "A mainnet key file is never overwritten — if it is funded, replacing\n"
            "it destroys access to the ADA it controls. If you truly intend a new\n"
            "key, move the old file aside yourself, deliberately.",
            file=sys.stderr,
        )
        return 1

    # 2. Generate + write the standard .skey JSON envelope (0600 from birth).
    sk = PaymentSigningKey.generate()
    address = derive_mainnet_address(sk)
    with os.fdopen(fd, "w") as f:
        f.write(sk.to_json())
    os.chmod(KEY_PATH, stat.S_IRUSR | stat.S_IWUSR)  # 600

    # 3. Round-trip verification WITHOUT printing key material.
    with open(KEY_PATH) as f:
        sk_back = PaymentSigningKey.from_json(f.read())
    assert derive_mainnet_address(sk_back) == address, "round-trip address mismatch"

    # 4. Print ONLY safe output: the public address, never the secret.
    print("round-trip OK")
    print(address)
    print()
    print("NEXT: pin this address as GRANTLAYER_CARDANO_EXPECTED_ADDRESS, copy the")
    print("64-hex seed to paper, prove it with --verify-backup — all BEFORE funding.")
    return 0


def verify_backup(expected_address: str) -> int:
    """Prove a paper backup reconstructs the key — in memory, writing NOTHING.

    The operator types the 64 hex chars from the PAPER copy. The envelope is
    rebuilt around them in memory, the mainnet address derived, and compared to
    the pinned expected address. Neither the hex nor the JSON is ever printed.
    """
    seed_hex = getpass.getpass("64-hex seed from the PAPER backup (input hidden): ")
    seed_hex = seed_hex.strip().lower().replace(" ", "")
    if len(seed_hex) != 64 or any(c not in "0123456789abcdef" for c in seed_hex):
        print("INVALID: expected exactly 64 hex characters.", file=sys.stderr)
        return 1

    envelope = json.dumps(
        {
            "type": KEY_TYPE,
            "description": KEY_TYPE,
            "cborHex": CBOR_PREFIX + seed_hex,
        }
    )
    sk = PaymentSigningKey.from_json(envelope)
    derived = derive_mainnet_address(sk)

    print(f"derived address : {derived}")
    print(f"expected address: {expected_address}")
    if derived == expected_address:
        print("MATCH — the paper backup reconstructs this wallet exactly.")
        return 0
    print("MISMATCH — the paper copy does NOT reconstruct the expected wallet.")
    print("Do NOT fund until a re-copied backup verifies. Check for transcription")
    print("errors (0/O, 1/l, missing chars) and copy again from the key file.")
    return 1


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="gen_mainnet_wallet.py",
        description=(
            "Generate the Cardano MAINNET anchoring wallet (default), or prove a "
            "paper seed backup with --verify-backup. Generation refuses to run if "
            f"{KEY_PATH} already exists."
        ),
    )
    parser.add_argument(
        "--verify-backup",
        action="store_true",
        help="verify a paper 64-hex seed backup (in memory; writes nothing)",
    )
    parser.add_argument(
        "--expected-address",
        default=None,
        help="the pinned addr1... address the backup must derive to "
        "(required with --verify-backup)",
    )
    args = parser.parse_args()

    if args.verify_backup:
        if not args.expected_address:
            parser.error("--verify-backup requires --expected-address")
        return verify_backup(args.expected_address)
    return generate()


if __name__ == "__main__":
    sys.exit(main())
