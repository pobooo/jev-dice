#!/usr/bin/env python3
"""Build a varied, balanced animal-description dataset."""

from __future__ import annotations

import json
import re
from pathlib import Path

OUT = Path(__file__).resolve().parent.parent / "data" / "animal_descriptions.jsonl"
ANIMALS = ["cat", "dog", "bird", "fish", "horse", "cow"]

DATA: dict[str, dict[str, list[str]]] = {
    "cat": {
        "clear": [
            "This small pet purrs while kneading a blanket with its paws.",
            "Whiskers frame its face, and it uses a litter box indoors.",
            "It arches its back, retracts its claws, and stalks mice at night.",
            "The furry pet meows for food and naps on a sunny windowsill.",
        ],
        "medium": [
            "A small agile pet silently climbs furniture and lands on its feet.",
            "This independent house pet grooms itself with a rough tongue.",
            "At dusk, the compact predator watches the floor for tiny rodents.",
            "The household companion has pointed ears and likes scratching posts.",
        ],
        "ambiguous": [
            "A quiet furry companion curls up on a warm lap.",
            "The small four-legged pet waits beside an empty food bowl.",
            "An agile domestic animal watches movement from under a chair.",
            "This soft-coated companion spends much of the afternoon asleep.",
        ],
    },
    "dog": {
        "clear": [
            "This loyal pet barks at strangers and wags its tail when excited.",
            "It fetches thrown sticks, pants after running, and wears a leash.",
            "The household companion guards the door and responds to a whistle.",
            "It follows scent trails with its nose and may howl at sirens.",
        ],
        "medium": [
            "This social pet eagerly greets its owner and enjoys long walks.",
            "A trainable companion sits on command and waits for a treat.",
            "The four-legged helper can guide people or search for missing objects.",
            "This energetic domestic animal digs in the yard and chases balls.",
        ],
        "ambiguous": [
            "A friendly furry companion waits by the front door.",
            "The pet follows its owner from room to room.",
            "This four-legged animal enjoys attention and outdoor exercise.",
            "A domestic companion sleeps near the family at night.",
        ],
    },
    "bird": {
        "clear": [
            "This feathered creature has a beak, wings, and builds a nest.",
            "It lays hard-shelled eggs and sings from a tree branch.",
            "The lightweight animal flaps through the air and perches on twigs.",
            "Its body is covered in feathers, and it pecks seeds from the ground.",
        ],
        "medium": [
            "A small creature perches above the ground and calls at sunrise.",
            "It gathers grass and small sticks to make a home for its young.",
            "This two-legged animal hops along branches searching for seeds.",
            "The creature spreads its wings before leaving the rooftop.",
        ],
        "ambiguous": [
            "A small animal makes repeated calls from high in a tree.",
            "The light creature rests on a narrow branch.",
            "It visits a garden feeder early each morning.",
            "This animal moves quickly between trees and rooftops.",
        ],
    },
    "fish": {
        "clear": [
            "This aquatic animal breathes through gills and swims with fins.",
            "Scales cover its body as it moves through water using its tail.",
            "It lives underwater, lacks legs, and takes oxygen through gills.",
            "The cold-blooded swimmer has fins on its body and a streamlined shape.",
        ],
        "medium": [
            "This water-dwelling creature darts through a school beneath the surface.",
            "The animal glides around an aquarium and is fed small flakes.",
            "It moves through a pond by sweeping its tail from side to side.",
            "This small aquatic creature stays submerged throughout its life.",
        ],
        "ambiguous": [
            "A silent animal moves below the surface of a pond.",
            "The small creature lives in a glass tank filled with water.",
            "It travels in groups through the open water.",
            "This animal is commonly seen moving beneath a lake's surface.",
        ],
    },
    "horse": {
        "clear": [
            "This large hoofed animal has a mane and carries a rider in a saddle.",
            "It gallops on four long legs and is controlled with reins.",
            "The stable animal neighs, wears horseshoes, and pulls a carriage.",
            "A rider mounts this powerful animal and holds its bridle.",
        ],
        "medium": [
            "This tall grazing animal runs quickly across an open field.",
            "The large domesticated animal lives in a stable and eats hay.",
            "It has long legs, a flowing tail, and is used for riding.",
            "The muscular hoofed animal can jump fences at an equestrian event.",
        ],
        "ambiguous": [
            "A large four-legged animal grazes in a fenced field.",
            "This strong farm animal eats hay and needs a spacious shelter.",
            "The tall animal runs across grass with a person on its back.",
            "A domesticated grazer stands quietly near a wooden fence.",
        ],
    },
    "cow": {
        "clear": [
            "This large farm animal moos and is milked in a dairy barn.",
            "It chews cud, has a broad muzzle, and produces milk for people.",
            "The hoofed livestock animal grazes in herds and may have an udder.",
            "This bovine farm animal gives birth to calves and feeds on pasture.",
        ],
        "medium": [
            "A heavy farm animal spends the day grazing and chewing cud.",
            "This domesticated grazer lives in a barn and is raised for dairy.",
            "The broad-bodied herd animal has cloven hooves and eats grass.",
            "Farmers guide this large livestock animal into a milking area.",
        ],
        "ambiguous": [
            "A large farm animal grazes slowly in a green pasture.",
            "This heavy four-legged grazer lives with a herd.",
            "The domesticated animal eats hay beside a barn.",
            "A broad-bodied animal stands behind a fence on a farm.",
        ],
    },
}


def main() -> None:
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    forbidden = re.compile(r"\b(" + "|".join(ANIMALS) + r")s?\b", re.I)
    for animal in ANIMALS:
        for clarity in ("clear", "medium", "ambiguous"):
            descriptions = DATA[animal][clarity]
            assert len(descriptions) == 4
            for index, text in enumerate(descriptions, 1):
                if forbidden.search(text):
                    raise SystemExit(f"animal name leaked in: {text}")
                if text in seen:
                    raise SystemExit(f"duplicate description: {text}")
                seen.add(text)
                rows.append(
                    {
                        "id": f"{animal}-{clarity}-{index:02d}",
                        "target": animal,
                        "clarity": clarity,
                        "text": text,
                    }
                )
    OUT.write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows)
    )
    print(f"wrote {len(rows)} unique descriptions to {OUT}")


if __name__ == "__main__":
    main()
