from flask import Flask, render_template, request, redirect, url_for, session, flash, send_file
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
import os
import datetime
import pandas as pd
import matplotlib.pyplot as plt
from io import BytesIO
import matplotlib

# Configurar matplotlib para no usar interfaz gráfica
matplotlib.use('Agg')

app = Flask(__name__)
app.secret_key = 'supersecretkey'

# Actualiza la cadena de conexión con tus datos reales
app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql+pymysql://root:1234@localhost/mi_base'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# MODELOS DE DATOS
class Profesor(db.Model):
    __tablename__ = 'profesores'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(512), nullable=False)
    grado = db.Column(db.String(20))
    seccion = db.Column(db.String(20))

class Alumno(db.Model):
    __tablename__ = 'alumnos'
    id = db.Column(db.Integer, primary_key=True)
    codigo = db.Column(db.String(20), unique=True, nullable=False)
    nombres = db.Column(db.String(100), nullable=False)
    apellidos = db.Column(db.String(100), nullable=False)
    grado = db.Column(db.String(20), nullable=False)
    seccion = db.Column(db.String(20), nullable=False)

class Asistencia(db.Model):
    __tablename__ = 'asistencia'
    id = db.Column(db.Integer, primary_key=True)
    fecha_real = db.Column(db.Date, nullable=False)
    fecha_ingresada = db.Column(db.Date, nullable=False)
    alumno_id = db.Column(db.Integer, db.ForeignKey('alumnos.id'), nullable=False)
    estado = db.Column(db.String(20), nullable=False)
    alumno = db.relationship('Alumno', backref=db.backref('asistencias', lazy=True))

# INICIALIZACIÓN DE LA BASE DE DATOS
def init_database():
    db.create_all()
    admin = Profesor.query.filter_by(username='admin').first()
    if not admin:
        admin = Profesor(username='admin', password=generate_password_hash('admin123'))
        db.session.add(admin)
        db.session.commit()

# GENERAR DATOS PARA DASHBOARD
def generate_dashboard_data():
    asistencias = Asistencia.query.all()
    total_alumnos = Alumno.query.count()
    if not asistencias:
        indicadores = {
            'total_alumnos': total_alumnos,
            'top_ausentes': {},
            'profesores_no_asistencia': []
        }
        return [], [], indicadores
    data = [{
        'Grado': a.alumno.grado,
        'Sección': a.alumno.seccion,
        'Estado': a.estado
    } for a in asistencias]
    df = pd.DataFrame(data)
    pivot = pd.pivot_table(df, index=['Grado', 'Sección'], columns='Estado', aggfunc=len, fill_value=0)
    pivot.reset_index(inplace=True)
    pivot['Asistencias'] = (pivot.get('Presente', 0) +
                            pivot.get('Ausente', 0) +
                            pivot.get('Permiso', 0) +
                            pivot.get('En IE', 0) +
                            pivot.get('En Revisión', 0))  # Se suma el nuevo estado "En Revisión"
    asistencia_total = pivot.to_dict(orient='records')
    df_ausentes = pd.DataFrame([{'Código': a.alumno.codigo, 'Ausente': 1 if a.estado.lower()=='ausente' else 0}
                                for a in asistencias])
    top_ausentes = df_ausentes.groupby('Código').sum().sort_values('Ausente', ascending=False).head(5)['Ausente'].to_dict()
    profesores_no_asistencia = []  # Aquí puedes definir tu lógica para profesores sin registro
    indicadores = {
        'total_alumnos': total_alumnos,
        'top_ausentes': top_ausentes,
        'profesores_no_asistencia': profesores_no_asistencia
    }
    return asistencia_total, [], indicadores

# RUTAS DE LA APLICACIÓN
@app.route('/', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        profesor = Profesor.query.filter_by(username=username).first()
        if profesor and check_password_hash(profesor.password, password):
            session['username'] = username
            if username == 'admin':
                return redirect(url_for('dashboard'))
            else:
                return redirect(url_for('asistencia'))
        else:
            flash('Usuario o contraseña incorrectos.', 'danger')
    return render_template('login.html')

@app.route('/dashboard')
def dashboard():
    if 'username' not in session or session['username'] != 'admin':
        flash("Acceso denegado: Solo el administrador puede ver el dashboard.", "danger")
        return redirect(url_for('login'))
    asistencia_total, alertas, indicadores = generate_dashboard_data()
    return render_template('dashboard.html', username=session['username'],
                           asistencia_total=asistencia_total, alertas=alertas, indicadores=indicadores)

@app.route('/asistencia', methods=['GET', 'POST'])
def asistencia():
    if 'username' not in session:
        return redirect(url_for('login'))
    fecha_actual = datetime.date.today().strftime("%Y-%m-%d")
    # Si el usuario no es admin, forzar el uso de su grado y sección asignados
    if session['username'] != 'admin':
        profesor = Profesor.query.filter_by(username=session['username']).first()
        assigned_grado = profesor.grado
        assigned_seccion = profesor.seccion
    else:
        assigned_grado = None
        assigned_seccion = None

    if request.method == 'POST':
        # Para profesores, ignorar los datos del formulario y usar los asignados
        if session['username'] != 'admin':
            grado = assigned_grado
            seccion = assigned_seccion
        else:
            grado = request.form['grado']
            seccion = request.form['seccion']
        fecha_ingresada = request.form['fecha']
        # Para profesores, siempre se registra para la fecha actual; para admin, se puede elegir la fecha
        if session['username'] == 'admin':
            fecha_real = datetime.datetime.strptime(fecha_ingresada, "%Y-%m-%d").date()
        else:
            fecha_real = datetime.date.today()
        registros = Asistencia.query.join(Alumno).filter(
            Asistencia.fecha_real == fecha_real,
            Alumno.grado == grado,
            Alumno.seccion == seccion
        ).all()
        if registros and session['username'] != 'admin':
            flash("⚠️ Ya se registró asistencia para este día, grado y sección.", "warning")
            return redirect(url_for('asistencia'))
        alumnos = Alumno.query.filter_by(grado=grado, seccion=seccion).all()
        if not alumnos:
            flash("No se encontraron alumnos para este grado y sección.", "warning")
            return redirect(url_for('asistencia'))
        alumnos_data = []
        for a in alumnos:
            alumnos_data.append({
                "Código": a.codigo,
                "Nombres": a.nombres,
                "Apellidos": a.apellidos,
                "Grado": a.grado,
                "Sección": a.seccion
            })
        return render_template('asistencia.html', alumnos=alumnos_data,
                               fecha=fecha_ingresada, fecha_actual=fecha_actual,
                               grado=grado, seccion=seccion)
    # GET request: para profesores, prellenar con su grado y sección asignados
    if session['username'] != 'admin':
        grado = assigned_grado
        seccion = assigned_seccion
    else:
        grado = ''
        seccion = ''
    return render_template('asistencia.html', alumnos=[], fecha_actual=fecha_actual, grado=grado, seccion=seccion)

@app.route('/registrar_asistencia', methods=['POST'])
def registrar_asistencia():
    if 'username' not in session:
        return redirect(url_for('login'))
    try:
        # Para admin, permitir elegir la fecha; para profesores, usar la fecha actual
        if session['username'] == 'admin':
            fecha_real = datetime.datetime.strptime(request.form['fecha'], "%Y-%m-%d").date()
        else:
            fecha_real = datetime.date.today()
        fecha_ingresada = datetime.datetime.strptime(request.form['fecha'], "%Y-%m-%d").date()
        grado = request.form['grado']
        seccion = request.form['seccion']

        # Validar que profesores solo registren asistencia para su sección asignada
        if session['username'] != 'admin':
            profesor = Profesor.query.filter_by(username=session['username']).first()
            if grado != profesor.grado or seccion != profesor.seccion:
                flash("No tienes permisos para registrar asistencia para esta sección.", "danger")
                return redirect(url_for('asistencia'))

        registros = Asistencia.query.join(Alumno).filter(
            Asistencia.fecha_real == fecha_real,
            Alumno.grado == grado,
            Alumno.seccion == seccion
        ).all()
        alumnos = Alumno.query.filter_by(grado=grado, seccion=seccion).all()
        if not alumnos:
            flash("No se encontraron alumnos para este grado y sección.", "warning")
            return redirect(url_for('asistencia'))

        if registros and session['username'] != 'admin':
            flash("⚠️ Asistencia ya registrada para este día, grado y sección.", "warning")
            return redirect(url_for('asistencia'))
        elif registros and session['username'] == 'admin':
            # Para admin: actualizar registros existentes o crearlos si faltan
            for alumno in alumnos:
                estado = request.form.get(f"estado_{alumno.codigo}", 'Ausente')
                registro = Asistencia.query.filter_by(fecha_real=fecha_real, alumno_id=alumno.id).first()
                if registro:
                    registro.estado = estado
                    registro.fecha_ingresada = fecha_ingresada
                else:
                    nuevo_registro = Asistencia(
                        fecha_real=fecha_real,
                        fecha_ingresada=fecha_ingresada,
                        alumno_id=alumno.id,
                        estado=estado
                    )
                    db.session.add(nuevo_registro)
        else:
            for alumno in alumnos:
                estado = request.form.get(f"estado_{alumno.codigo}", 'Ausente')
                nuevo_registro = Asistencia(
                    fecha_real=fecha_real,
                    fecha_ingresada=fecha_ingresada,
                    alumno_id=alumno.id,
                    estado=estado
                )
                db.session.add(nuevo_registro)
        db.session.commit()
        flash("Asistencia registrada correctamente.", "success")
        return redirect(url_for('dashboard') if session['username'] == 'admin' else url_for('asistencia'))
    except Exception as e:
        db.session.rollback()
        flash(f"Error al registrar asistencia: {e}", "danger")
        return redirect(url_for('asistencia'))

@app.route('/editar_asistencia/<int:asistencia_id>', methods=['GET', 'POST'])
def editar_asistencia(asistencia_id):
    # Solo el administrador puede editar asistencia sin restricciones
    if 'username' not in session or session['username'] != 'admin':
        flash("Acceso denegado: Solo el administrador puede editar asistencia.", "danger")
        return redirect(url_for('login'))
    registro = Asistencia.query.get_or_404(asistencia_id)
    if request.method == 'POST':
        try:
            registro.estado = request.form['estado']
            nueva_fecha = request.form.get('fecha_ingresada')
            if nueva_fecha:
                registro.fecha_ingresada = datetime.datetime.strptime(nueva_fecha, "%Y-%m-%d").date()
            db.session.commit()
            flash("Registro actualizado correctamente.", "success")
            return redirect(url_for('dashboard'))
        except Exception as e:
            db.session.rollback()
            flash(f"Error al actualizar el registro: {e}", "danger")
            return redirect(url_for('editar_asistencia', asistencia_id=asistencia_id))
    return render_template('editar_asistencia.html', registro=registro)

@app.route('/subir_asistencia_anterior', methods=['GET', 'POST'])
def subir_asistencia_anterior():
    if 'username' not in session or session['username'] != 'admin':
        flash("Acceso denegado.", "danger")
        return redirect(url_for('login'))
    if request.method == 'POST':
        try:
            fecha = datetime.datetime.strptime(request.form['fecha'], "%Y-%m-%d").date()
            grado = request.form['grado']
            seccion = request.form['seccion']
            alumnos = Alumno.query.filter_by(grado=grado, seccion=seccion).all()
            for alumno in alumnos:
                estado = request.form.get(f"estado_{alumno.codigo}", 'Ausente')
                nuevo_registro = Asistencia(
                    fecha_real=fecha,
                    fecha_ingresada=fecha,
                    alumno_id=alumno.id,
                    estado=estado
                )
                db.session.add(nuevo_registro)
            db.session.commit()
            flash("Asistencias de período anterior subidas correctamente.", "success")
            return redirect(url_for('dashboard'))
        except Exception as e:
            db.session.rollback()
            flash(f"Error al subir asistencia: {e}", "danger")
            return redirect(url_for('subir_asistencia_anterior'))
    return render_template('subir_asistencia_anterior.html')

@app.route('/descargar', methods=['GET', 'POST'])
def descargar():
    if 'username' not in session or session['username'] != 'admin':
        flash("Acceso denegado.", "danger")
        return redirect(url_for('login'))
    if request.method == 'POST':
        tipo_reporte = request.form['tipo_reporte']
        grado = request.form.get('grado')
        seccion = request.form.get('seccion')
        fecha_inicio = request.form.get('fecha_inicio')
        fecha_fin = request.form.get('fecha_fin')
        
        query = db.session.query(Asistencia, Alumno).join(Alumno)
        if fecha_inicio:
            fecha_inicio_dt = datetime.datetime.strptime(fecha_inicio, "%Y-%m-%d").date()
            query = query.filter(Asistencia.fecha_real >= fecha_inicio_dt)
        if fecha_fin:
            fecha_fin_dt = datetime.datetime.strptime(fecha_fin, "%Y-%m-%d").date()
            query = query.filter(Asistencia.fecha_real <= fecha_fin_dt)
        if grado:
            query = query.filter(Alumno.grado == grado)
        if seccion:
            query = query.filter(Alumno.seccion == seccion)
        
        records = []
        for asistencia, alumno in query.all():
            records.append({
                'Fecha Real': asistencia.fecha_real.strftime("%Y-%m-%d"),
                'Fecha Ingresada': asistencia.fecha_ingresada.strftime("%Y-%m-%d"),
                'Código': alumno.codigo,
                'Nombres': alumno.nombres,
                'Apellidos': alumno.apellidos,
                'Grado': alumno.grado,
                'Sección': alumno.seccion,
                'Estado': asistencia.estado
            })
        df_asistencia = pd.DataFrame(records)
        
        if tipo_reporte == 'listado_alumnos':
            alumnos_query = Alumno.query
            if grado:
                alumnos_query = alumnos_query.filter_by(grado=grado)
            if seccion:
                alumnos_query = alumnos_query.filter_by(seccion=seccion)
            alumnos_records = [{
                'Código': a.codigo,
                'Nombres': a.nombres,
                'Apellidos': a.apellidos,
                'Grado': a.grado,
                'Sección': a.seccion
            } for a in alumnos_query.all()]
            df_alumnos = pd.DataFrame(alumnos_records)
            file_path = f'Listado_Alumnos_{grado}_{seccion}.xlsx'
            df_alumnos.to_excel(file_path, index=False)
        elif tipo_reporte == 'asistencia_trabajada':
            if not df_asistencia.empty:
                pivote = df_asistencia.pivot_table(index=['Nombres', 'Apellidos'],
                                                    columns='Fecha Real', values='Estado',
                                                    aggfunc='first', fill_value='-')
                pivote['Porcentaje Asistencia'] = (pivote.apply(lambda row: (row == 'Presente').sum() / len(row), axis=1) * 100).round(2)
                file_path = f'Asistencia_Trabajada_{grado}_{seccion}.xlsx'
                pivote.to_excel(file_path)
            else:
                flash("No hay registros en el período seleccionado.", "danger")
                return redirect(url_for('descargar'))
        elif tipo_reporte == 'reporte_alumno':
            codigo = request.form.get('codigo')
            df_alumno = df_asistencia[df_asistencia['Código'] == codigo]
            if df_alumno.empty:
                flash("No hay registros para este alumno en el período seleccionado.", "danger")
                return redirect(url_for('descargar'))
            file_path = f'Reporte_Alumno_{codigo}.xlsx'
            df_alumno.to_excel(file_path, index=False)
        return send_file(file_path, as_attachment=True)
    return render_template('descargar.html')

@app.route('/logout')
def logout():
    session.pop('username', None)
    return redirect(url_for('login'))

if __name__ == '__main__':
    with app.app_context():
        init_database()
    # Para producción en el VPS, se recomienda configurar:
    # app.run(debug=False, host='0.0.0.0', port=5000)
    app.run(debug=True, host='0.0.0.0', port=5000)
