import os
import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings")
django.setup()

from topeducation.inspectors.courses_inspector import fetch_and_parse

endpoint = os.environ["COURSES_EXTERNAL_ENDPOINT"]
courses = fetch_and_parse(endpoint, timeout=90)

print("Total:", len(courses))
if courses:
    c = courses[0]
    print("Sample:", c.external_id, c.nombre, c.imagen, c.skills[:5])
