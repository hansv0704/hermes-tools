import os
for r, d, fs in os.walk('skills'):
    for f in fs:
        if f.endswith('.py'):
            p = os.path.join(r, f)
            with open(p, 'r', encoding='utf-8') as file:
                c = file.read()
            nc = c.replace("'STRING'", "'string'").replace('"STRING"', '"string"').replace("'OBJECT'", "'object'").replace('"OBJECT"', '"object"').replace("'INTEGER'", "'integer'").replace('"INTEGER"', '"integer"').replace("'NUMBER'", "'number'").replace('"NUMBER"', '"number"').replace("'BOOLEAN'", "'boolean'").replace('"BOOLEAN"', '"boolean"').replace("'ARRAY'", "'array'").replace('"ARRAY"', '"array"')
            if nc != c:
                with open(p, 'w', encoding='utf-8') as file:
                    file.write(nc)
