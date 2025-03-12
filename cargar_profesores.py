import pandas as pd
from app import db, Profesor, app
from werkzeug.security import generate_password_hash

# Lee el archivo CSV; ajusta el separador si fuera necesario
df = pd.read_csv('profesores.csv', sep=',')

with app.app_context():
    for index, row in df.iterrows():
        # Verificamos si el usuario ya existe para evitar duplicados
        prof_existente = Profesor.query.filter_by(username=row['username']).first()
        if not prof_existente:
            profesor = Profesor(
                username=row['username'],
                password=generate_password_hash(row['password']),
                grado=row['Grado'],
                seccion=row['Sección']
            )
            db.session.add(profesor)
    db.session.commit()
    print("Se han insertado {} registros en la tabla 'profesores'.".format(len(df)))
