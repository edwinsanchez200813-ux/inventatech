from flask import Flask, render_template, request, redirect, url_for, flash, session, send_file
import io
import mysql.connector
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors

app = Flask(__name__)
app.secret_key = 'clave_secreta_inventatech'

def get_db_connection():
    connection = mysql.connector.connect(
        host="localhost",
        user="root",
        password="1234",  # Tu contraseña de MySQL
        database="inventatech_db"
    )
    return connection

@app.route('/')
def index():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    cursor.execute("""
        SELECT p.id, p.nombre, p.sku, p.costo, p.precio, p.stock, c.nombre AS categoria, p.categoria_id 
        FROM productos p 
        LEFT JOIN categorias c ON p.categoria_id = c.id
        ORDER BY p.id DESC
    """)
    productos = cursor.fetchall()
    
    cursor.execute("SELECT * FROM categorias")
    categorias = cursor.fetchall()

    cursor.execute("""
        SELECT v.id, p.nombre AS producto, p.sku, v.cantidad, v.precio_unitario, v.total, v.fecha 
        FROM ventas v
        JOIN productos p ON v.producto_id = p.id
        ORDER BY v.fecha DESC
    """)
    ventas = cursor.fetchall()

    total_ingresos = sum(v['total'] for v in ventas)
    
    cursor.close()
    conn.close()
    
    return render_template('index.html', productos=productos, categorias=categorias, ventas=ventas, total_ingresos=total_ingresos)

@app.route('/descargar-reporte-pdf')
def descargar_reporte_pdf():
    conexion = get_db_connection() 
    cursor = conexion.cursor(dictionary=True)
    
    # 1. Consultar ventas y calcular totales y ganancias
    cursor.execute("""
        SELECT v.*, p.nombre as producto_nombre, p.costo, p.precio 
        FROM ventas v 
        JOIN productos p ON v.producto_id = p.id
    """)
    ventas = cursor.fetchall()
    
    total_ventas = sum(v['cantidad'] * v['precio'] for v in ventas)
    total_costos = sum(v['cantidad'] * v['costo'] for v in ventas)
    ganancia_neta = total_ventas - total_costos
    
    margen = (ganancia_neta / total_ventas * 100) if total_ventas > 0 else 0
    
    # 2. Encontrar el producto más vendido
    cursor.execute("""
        SELECT p.nombre, SUM(v.cantidad) as total_vendidos 
        FROM ventas v 
        JOIN productos p ON v.producto_id = p.id 
        GROUP BY p.id 
        ORDER BY total_vendidos DESC LIMIT 1
    """)
    top_producto = cursor.fetchone()
    nombre_top = top_producto['nombre'] if top_producto else "Sin ventas registradas"

    cursor.close()
    conexion.close()

    # 3. Generar el PDF en una sola página con ReportLab
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, rightMargin=40, leftMargin=40, topMargin=40, bottomMargin=40)
    elementos = []
    
    estilos = getSampleStyleSheet()
    
    estilo_titulo = ParagraphStyle('Titulo', parent=estilos['Heading1'], fontSize=20, textColor=colors.HexColor('#0f172a'), spaceAfter=4)
    estilo_sub = ParagraphStyle('Sub', parent=estilos['Normal'], fontSize=10, textColor=colors.HexColor('#64748b'), spaceAfter=20)
    estilo_seccion = ParagraphStyle('Seccion', parent=estilos['Heading2'], fontSize=13, textColor=colors.HexColor('#1e293b'), spaceBefore=15, spaceAfter=8)
    estilo_cuerpo = ParagraphStyle('Cuerpo', parent=estilos['Normal'], fontSize=10, textColor=colors.HexColor('#334155'), leading=14, spaceAfter=10)
    
    # Estilos específicos para celdas de la tabla (evitan solapamientos)
    estilo_th = ParagraphStyle('TH', parent=estilos['Normal'], fontSize=9, textColor=colors.whitesmoke, fontName='Helvetica-Bold')
    estilo_td = ParagraphStyle('TD', parent=estilos['Normal'], fontSize=9, textColor=colors.HexColor('#334155'), fontName='Helvetica', leading=11)
    
    # Encabezado Ejecutivo
    elementos.append(Paragraph("<b>InventaTech — Reporte Ejecutivo de Gestión</b>", estilo_titulo))
    elementos.append(Paragraph("Informe de rendimiento financiero, control de inventarios y análisis operativo.", estilo_sub))
    
    # Texto de Análisis Descriptivo
    elementos.append(Paragraph("<b>1. Resumen de Desempeño Operativo</b>", estilo_seccion))
    texto_analisis = (
        f"Durante el periodo actual de operaciones, el sistema ha registrado un volumen de ventas consolidado en <b>${total_ventas:,.0f} COP</b>, "
        f"con una inversión acumulada en costos de inventario de <b>${total_costos:,.0f} COP</b>. Esto genera una utilidad neta estimada de "
        f"<b>${ganancia_neta:,.0f} COP</b>, representando un margen de rentabilidad global del <b>{margen:.1f}%</b> sobre las transacciones efectuadas. "
        f"El artículo con mayor dinamismo comercial y preferencia por parte de los clientes ha sido <b>{nombre_top}</b>."
    )
    elementos.append(Paragraph(texto_analisis, estilo_cuerpo))
    
    # Tabla Financiera Detallada con Párrafos para control de texto
    elementos.append(Paragraph("<b>2. Indicadores Financieros Clave</b>", estilo_seccion))
    
    datos_resumen = [
        [Paragraph('Indicador / Métrica', estilo_th), Paragraph('Valor Financiero (COP)', estilo_th), Paragraph('Estado / Evaluación', estilo_th)],
        [Paragraph('Total Recaudado en Ventas', estilo_td), Paragraph(f"${total_ventas:,.0f}", estilo_td), Paragraph('Flujo de Ingresos Activo', estilo_td)],
        [Paragraph('Costo Total de Inversión', estilo_td), Paragraph(f"${total_costos:,.0f}", estilo_td), Paragraph('Capital Operativo Invertido', estilo_td)],
        [Paragraph('Ganancia / Utilidad Neta', estilo_td), Paragraph(f"${ganancia_neta:,.0f}", estilo_td), Paragraph(f"Margen: {margen:.1f}% (Saludable)", estilo_td)],
        [Paragraph('Producto Estrella (Top Sales)', estilo_td), Paragraph(str(nombre_top), estilo_td), Paragraph('Líder en Rotación de Stock', estilo_td)]
    ]
    
    # Redistribuimos el ancho de columnas (Total 532 puntos disponibles)
    tabla_resumen = Table(datos_resumen, colWidths=[150, 180, 202])
    tabla_resumen.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#1e293b')),
        ('ALIGN', (0,0), (-1,-1), 'LEFT'),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('BOTTOMPADDING', (0,0), (-1,0), 8),
        ('TOPPADDING', (0,0), (-1,0), 8),
        ('BACKGROUND', (0,1), (-1,-1), colors.HexColor('#f8fafc')),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.HexColor('#ffffff'), colors.HexColor('#f1f5f9')]),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#cbd5e1')),
        ('BOTTOMPADDING', (0,1), (-1,-1), 6),
        ('TOPPADDING', (0,1), (-1,-1), 6)
    ]))
    
    elementos.append(tabla_resumen)
    elementos.append(Spacer(1, 10))
    
    # Sugerencias y Recomendaciones Estratégicas
    elementos.append(Paragraph("<b>3. Sugerencias y Recomendaciones Estratégicas</b>", estilo_seccion))
    texto_recomendaciones = (
        "• <b>Optimización de Stock:</b> Se recomienda asegurar un reabastecimiento prioritario del producto líder (" + str(nombre_top) + ") "
        "para evitar quiebres de inventario ante la alta demanda sostenida.<br/>"
        "• <b>Control de Costos:</b> Monitorear de cerca los costos de adquisición de los componentes para proteger el margen de ganancia actual superior al 20%.<br/>"
        "• <b>Estrategia Comercial:</b> Impulsar campañas de rotación para aquellos artículos de menor salida registrados en el sistema de inventarios."
    )
    elementos.append(Paragraph(texto_recomendaciones, estilo_cuerpo))
    
    # Pie de página integrado
    elementos.append(Spacer(1, 20))
    estilo_footer = ParagraphStyle('Footer', parent=estilos['Normal'], fontSize=8, textColor=colors.HexColor('#94a3b8'), alignment=1)
    elementos.append(Paragraph("InventaTech POS & Inventory Management — Reporte generado automáticamente desde Base de Datos Local MySQL.", estilo_footer))
    
    doc.build(elementos)
    
    buffer.seek(0)
    return send_file(buffer, as_attachment=True, download_name="Reporte_Gerencial_InventaTech.pdf", mimetype='application/pdf')

@app.route('/login', methods=['POST'])
def login():
    data = request.form if request.form else request.get_json()
    usuario = data.get('email') or data.get('username')
    contrasena = data.get('password')
    
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM usuarios WHERE username = %s AND password = %s", (usuario, contrasena))
    user = cursor.fetchone()
    cursor.close()
    conn.close()
    
    if user:
        session['usuario'] = user['username']
        session['rol'] = user['rol']
        return redirect(url_for('index'))
    else:
        return "Credenciales incorrectas. <a href='/'>Volver</a>", 401

@app.route('/agregar_producto', methods=['POST'])
def agregar_producto():
    if 'usuario' not in session:
        return redirect(url_for('index'))
        
    nombre = request.form['nombre']
    sku = request.form['sku']
    costo = float(request.form['costo'])
    precio = float(request.form['precio'])
    stock_nuevo = int(request.form['stock'])
    categoria_id = request.form['categoria_id']
    
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    # Verificar si el producto ya existe por su nombre exacto
    cursor.execute("SELECT * FROM productos WHERE nombre = %s", (nombre,))
    producto_existente = cursor.fetchone()
    
    if producto_existente:
        # Si ya existe, SUMAR al stock actual y actualizar precio/costo si es necesario
        nuevo_stock = producto_existente['stock'] + stock_nuevo
        cursor.execute(
            "UPDATE productos SET stock = %s, costo = %s, precio = %s WHERE id = %s",
            (nuevo_stock, costo, precio, producto_existente['id'])
        )
        flash(f"El producto ya existía. Se sumaron {stock_nuevo} unidades al stock (Total: {nuevo_stock}).", "success")
    else:
        # Si no existe, crear registro nuevo
        cursor.execute(
            "INSERT INTO productos (nombre, sku, costo, precio, stock, categoria_id) VALUES (%s, %s, %s, %s, %s, %s)",
            (nombre, sku, costo, precio, stock_nuevo, categoria_id)
        )
        flash(f"¡Producto registrado exitosamente!", "success")
        
    conn.commit()
    cursor.close()
    conn.close()
    return redirect(url_for('index'))

# RUTA PARA EDITAR PRODUCTO DIRECTAMENTE
@app.route('/editar_producto', methods=['POST'])
def editar_producto():
    if 'usuario' not in session:
        return redirect(url_for('index'))
        
    producto_id = request.form['producto_id']
    nuevo_precio = request.form['precio']
    nuevo_costo = request.form['costo']
    nuevo_stock = request.form['stock']
    
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE productos SET precio = %s, costo = %s, stock = %s WHERE id = %s", (nuevo_precio, nuevo_costo, nuevo_stock, producto_id))
    conn.commit()
    cursor.close()
    conn.close()
    
    flash("Producto actualizado correctamente.", "success")
    return redirect(url_for('index'))

@app.route('/vender_producto', methods=['POST'])
def vender_producto():
    if 'usuario' not in session:
        return redirect(url_for('index'))
        
    producto_id = request.form['producto_id']
    cantidad = int(request.form['cantidad'])
    
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    cursor.execute("SELECT * FROM productos WHERE id = %s", (producto_id,))
    prod = cursor.fetchone()
    
    if prod:
        if prod['stock'] >= cantidad:
            nuevo_stock = prod['stock'] - cantidad
            total_venta = cantidad * float(prod['precio'])
            
            cursor.execute("UPDATE productos SET stock = %s WHERE id = %s", (nuevo_stock, producto_id))
            cursor.execute(
                "INSERT INTO ventas (producto_id, cantidad, precio_unitario, total) VALUES (%s, %s, %s, %s)",
                (producto_id, cantidad, prod['precio'], total_venta)
            )
            conn.commit()
            flash(f"¡Venta realizada con éxito! Se descontaron {cantidad} unidades de {prod['nombre']}.", "success")
        else:
            flash(f"¡Error! Stock insuficiente. Solo quedan {prod['stock']} unidades disponibles.", "danger")
    
    cursor.close()
    conn.close()
    return redirect(url_for('index'))

@app.route('/eliminar/<int:id>')
def eliminar_producto(id):
    if 'usuario' not in session:
        return redirect(url_for('index'))
        
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM productos WHERE id = %s", (id,))
    conn.commit()
    cursor.close()
    conn.close()
    return redirect(url_for('index'))

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))

if __name__ == '__main__':
    app.run(debug=True)