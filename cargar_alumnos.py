import pandas as pd
from app import db, Alumno, app

# Lee el archivo CSV (si el separador es una coma, no es necesario especificar sep)
df = pd.read_csv('alumnos.csv', sep=';')

# Si tu CSV está separado por tabuladores, usa:
# df = pd.read_csv('alumnos.csv', sep='\t')

with app.app_context():
    for index, row in df.iterrows():
        alumno = Alumno(
            codigo=row['Código'],
            nombres=row['Nombres'],
            apellidos=row['Apellidos'],
            grado=row['Grado'],
            seccion=row['Sección']
        )
        db.session.add(alumno)
    db.session.commit()
    print("Se han insertado {} registros en la tabla 'alumnos'.".format(len(df)))
