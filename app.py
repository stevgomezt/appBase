# Módulos estándar
from datetime import date
import json
import logging
import re
import sys
import uuid
import base64

# Tipado
from typing import Union

# Librerías de terceros
import numpy as np
import pandas as pd
import altair as alt
import matplotlib.pyplot as plt
import plotly.express as px
import plotly.graph_objects as go
import plotly.colors as colors_plotly
from flask import Flask, request, jsonify, render_template, url_for
from google.cloud import storage
import streamlit as st

# Módulo personalizado
import validar_preprocesar_predecir_organizarrtados

# Aliases comunes
import pickle as pkl

# Para Botones sin recargar

# -----------------------------------------------------IAP GCP

app = Flask(__name__)

# -----------------------------------------------------

# Configure this environment variable via app.yaml
# CLOUD_STORAGE_BUCKET = os.environ['CLOUD_STORAGE_BUCKET']


# Define una ruta en un servidor web usando un decorador. En este caso, la ruta es la raíz ('/').
@app.route('/')
def index() -> str:
    # La función 'index' maneja las solicitudes a la ruta raíz y devuelve una respuesta como string.
    return """
    # Retorna un formulario HTML como respuesta.
    <form method="POST" action="/upload" enctype="multipart/form-data">
        # Campo de entrada para 'datos', donde los usuarios pueden ingresar o subir datos.
        <input type="datos" name="datos">
        # Botón de envío para enviar el formulario.
        <input type="submit">
    </form>
    """
# Esta función se utiliza en aplicaciones web, típicamente con frameworks como Flask, para definir lo que sucede cuando un usuario accede a la ruta raíz
# (por ejemplo, http://www.ejemplo.com/). En este caso, muestra un formulario HTML que permite a los usuarios cargar datos, los cuales se envían a la ruta
# /upload utilizando el método POST.
# -----------------------------------------------------

# Define una ruta '/upload' en el servidor web para manejar solicitudes POST.


@app.route('/upload', methods=['POST'])
def upload(csvdata, bucketname, blobname):
    # Crea un cliente para interactuar con Google Cloud Storage.
    client = storage.Client()

    # Obtiene el objeto 'bucket' (cubeta) de Google Cloud Storage especificado por 'bucketname'.
    bucket = client.get_bucket(bucketname)

    # Crea un objeto 'blob' en el 'bucket' especificado con el nombre 'blobname'.
    blob = bucket.blob(blobname)

    # Sube los datos 'csvdata' al 'blob' creado anteriormente.
    blob.upload_from_string(csvdata)

    # Formatea la ubicación del archivo en Google Cloud Storage para registrarla.
    gcslocation = 'gs://{}/{}'.format(bucketname, blobname)

    # Registra en el logging la ubicación del archivo subido.
    logging.info('Uploaded {} ...'.format(gcslocation))

    # Devuelve la ubicación del archivo subido como respuesta a la solicitud.
    return gcslocation

# Esta función maneja la subida de datos (en formato CSV) a un bucket específico en Google Cloud Storage. Se activa cuando se envía una solicitud POST a la ruta '/upload'.
# Los datos se suben a un archivo (blob) en el bucket especificado, y luego se devuelve la ubicación de este archivo en Google Cloud Storage.
# -----------------------------------------------------


# Define un manejador de errores para el código de estado HTTP 500 (Error Interno del Servidor).
@app.errorhandler(500)
def server_error(e: Union[Exception, int]) -> str:
    # Registra el error en el sistema de logging.
    logging.exception('An error occurred during a request.')

    # Devuelve una respuesta al cliente indicando que ocurrió un error interno.
    # Incluye una representación del error (e) y establece el código de estado HTTP a 500.
    return """
    An internal error occurred: <pre>{}</pre>
    See logs for full stacktrace.
    """.format(e), 500

# Esta función se activa cuando ocurre un error interno del servidor (código de estado 500) en tu aplicación web. Registra los detalles del error en el sistema de logging
# y devuelve un mensaje al usuario final que indica que se ha producido un error interno, mostrando también una representación del error para más detalles. El tipo de
# error (e) puede ser una excepción o un entero, y se muestra en el mensaje de error devuelto al usuario.

# -----------------------------------------------------


CERTS = None
AUDIENCE = None
# Los fragmentos de código CERTS = None y AUDIENCE = None son asignaciones de variables en Python. Aquí está la explicación de cada uno
# -----------------------------------------------------


def certs():
    """
    Devuelve un diccionario de certificados públicos actuales de Google para 
    validar JWTs firmados por Google. Dado que estos certificados cambian raramente, 
    el resultado se almacena en caché tras la primera solicitud para agilizar 
    respuestas subsiguientes.
    """
    import requests  # Importa el módulo requests para hacer solicitudes HTTP.

    global CERTS  # Declara que la variable CERTS es una variable global.

    # Verifica si CERTS todavía no tiene un valor asignado (es None).
    if CERTS is None:
        # Realiza una solicitud HTTP GET para obtener los certificados de Google.
        response = requests.get(
            'https://www.gstatic.com/iap/verify/public_key'
        )
        # Almacena la respuesta en formato JSON en la variable global CERTS.
        CERTS = response.json()

    # Devuelve el diccionario de certificados.
    return CERTS

# Esta función hace lo siguiente:

# Verifica si la variable global CERTS ya tiene un valor. Si no es así, significa que aún no se han recuperado los certificados.
# Si CERTS es None, realiza una solicitud HTTP GET a una URL específica que contiene los certificados públicos de Google.
# Convierte la respuesta a un formato JSON, que es un diccionario de los certificados, y almacena este diccionario en CERTS.
# Devuelve el diccionario de certificados.
# La idea detrás de esta implementación es utilizar la memorización para evitar solicitudes HTTP repetidas, almacenando los certificados la primera vez que se solicitan y reutilizándolos en solicitudes futuras. Esto mejora la eficiencia, especialmente si los certificados se necesitan con frecuencia y no cambian a menudo.
# -----------------------------------------------------


def get_metadata(item_name):
    """
    Devuelve una cadena con el valor de los metadatos del proyecto para el item_name.
    Consulta https://cloud.google.com/compute/docs/storing-retrieving-metadata para
    conocer los posibles valores de item_name.
    """
    import requests  # Importa el módulo requests para realizar solicitudes HTTP.

    # Define la URL base del servicio de metadatos de Google.
    endpoint = 'http://metadata.google.internal'
    # Especifica el camino al recurso de metadatos del proyecto.
    path = '/computeMetadata/v1/project/'
    # Agrega el nombre del ítem de metadatos solicitado al camino.
    path += item_name

    # Realiza una solicitud HTTP GET al servicio de metadatos.
    response = requests.get(
        '{}{}'.format(endpoint, path),
        # Incluye un encabezado específico requerido por Google.
        headers={'Metadata-Flavor': 'Google'}
    )

    # Obtiene el contenido de la respuesta como texto.
    metadata = response.text

    return metadata  # Devuelve el valor de los metadatos.

# Esta función realiza lo siguiente:

# Construye una URL específica utilizando el endpoint del servicio de metadatos de Google Cloud y el path que conduce a los metadatos del proyecto, agregando el item_name que se desea consultar.
# Envía una solicitud HTTP GET a esta URL. Importante notar que incluye un encabezado HTTP ('Metadata-Flavor': 'Google') que es necesario para autenticar la solicitud ante el servicio de metadatos de Google.
# Obtiene la respuesta de la solicitud y extrae el texto, que representa el valor de los metadatos solicitados.
# Devuelve el valor de los metadatos.
# La función es útil para recuperar información de configuración o de entorno específica del proyecto en Google Cloud, lo cual puede incluir detalles como ID del proyecto, nombre de la máquina, etc. La URL http://metadata.google.internal es una dirección interna utilizada dentro de las máquinas virtuales de Google Cloud para acceder a su servicio de metadatos.

# -----------------------------------------------------


def audience():
    """
    Devuelve el valor de 'audience' (propiedad 'aud' de JWT) para la instancia 
    actual en ejecución. Como esto requiere una búsqueda de metadatos, 
    el resultado se almacena en caché en la primera solicitud para 
    respuestas más rápidas en el futuro.
    """
    global AUDIENCE  # Declara AUDIENCE como una variable global.

    if AUDIENCE is None:  # Verifica si AUDIENCE aún no tiene un valor asignado.
        # Obtiene el número del proyecto actual llamando a get_metadata.
        project_number = get_metadata('numeric-project-id')

        # Obtiene el ID del proyecto actual llamando a get_metadata.
        project_id = get_metadata('project-id')

        # Formatea el valor de AUDIENCE utilizando el número y el ID del proyecto.
        AUDIENCE = '/projects/{}/apps/{}'.format(
            project_number, project_id
        )

    # Devuelve el valor de AUDIENCE.
    return AUDIENCE

# Esta función realiza lo siguiente:

# Verifica si la variable global AUDIENCE ya ha sido establecida. Si es None, procede a obtener los metadatos necesarios.
# Utiliza la función get_metadata() para obtener el número numérico del proyecto (numeric-project-id) y el ID del proyecto (project-id) de los metadatos de Google Cloud.
# Combina estos dos valores para formar el valor de AUDIENCE, que típicamente es una URL o un identificador único que representa a quién está destinado el JWT.
# Almacena este valor en AUDIENCE y lo devuelve. En llamadas futuras, si AUDIENCE ya tiene un valor, simplemente lo devuelve, evitando así búsquedas de metadatos adicionales.
# Esta funcionalidad es particularmente útil en entornos de Google Cloud, donde se necesita autenticar y autorizar aplicaciones y servicios, especialmente cuando se trabaja con APIs y JWTs.
# -----------------------------------------------------


def validate_assertion(assertion):
    """
    Verifica que la aserción JWT sea válida (correctamente firmada, para el 
    público correcto) y si es así, devuelve cadenas para el correo electrónico del 
    usuario solicitante y un ID de usuario persistente. Si no es válido, devuelve 
    None para cada campo.
    """
    from json import jwt  # Importa la biblioteca jwt para decodificar el JWT.

    try:
        # Intenta decodificar el JWT (aserción).
        info = jwt.decode(
            assertion,  # El JWT a ser validado.
            # Obtiene los certificados para verificar la firma del JWT.
            certs(),
            # Especifica el algoritmo de firma a utilizar.
            algorithms=['ES256'],
            # Obtiene el valor de 'audience' para la validación.
            audience=audience()
        )

        # Si es exitoso, devuelve el correo electrónico y el ID del usuario del JWT.
        return info['email'], info['sub']

    except Exception as e:
        # Si ocurre un error (por ejemplo, firma inválida, JWT caducado), se registra el error.
        print('Failed to validate assertion: {}'.format(e), file=sys.stderr)

        # Devuelve None para cada campo en caso de error.
        return None, None

# Esta función realiza lo siguiente:

# Intenta decodificar y validar el JWT proporcionado en el parámetro assertion.
# Utiliza la función certs() para obtener los certificados necesarios para verificar la firma del JWT.
# Especifica el algoritmo de firma ('ES256') que se debe usar en la validación.
# Utiliza la función audience() para obtener el valor de 'audience', que es crucial para asegurar que el JWT esté destinado para la audiencia correcta (es decir, tu aplicación o servicio).
# Si el JWT es válido, extrae y devuelve el correo electrónico (email) y el ID del usuario (sub) contenidos en el JWT.
# Si la validación falla por cualquier razón (como una firma incorrecta o un JWT expirado), se captura la excepción, se registra el error y se devuelven None, None.
# Esta función es útil para la autenticación y autorización en aplicaciones donde se utilizan JWTs para representar y verificar las identidades de los usuarios.
# -----------------------------------------------------


def download_excel(df_v, nombre='LogErrores', col=st):
    # Convierte el DataFrame 'df_v' en un archivo Excel y lo guarda con el nombre proporcionado.
    df_v.to_excel(nombre+'.xlsx', index=False)
    filename = nombre+'.xlsx'  # Almacena el nombre del archivo.

    # Abre el archivo Excel en modo de lectura binaria.
    with open(nombre+'.xlsx', 'rb') as file:
        contents = file.read()  # Lee el contenido del archivo.

    if col == st:
        # Si 'col' es igual a 'st', se asume que se está trabajando en la columna principal de Streamlit.
        # Genera el botón de descarga para la columna principal.
        download_button_str = download_button(contents, filename, nombre)
        # Añade el botón de descarga a la interfaz de usuario de Streamlit.
        st.markdown(download_button_str, unsafe_allow_html=True)

    else:
        # Si 'col' no es igual a 'st', se asume que se está trabajando en una columna específica de Streamlit.
        # Genera el botón de descarga para la columna especificada.
        download_button_str = download_button(contents, filename, nombre)
        # Añade el botón de descarga a la columna especificada en Streamlit.
        col.markdown(download_button_str, unsafe_allow_html=True)

# La función realiza las siguientes acciones:

# Convierte un DataFrame (df_v) en un archivo Excel y lo guarda con el nombre especificado (nombre), que por defecto es 'LogErrores'.
# Lee el contenido del archivo Excel creado.
# Dependiendo del parámetro col, que determina dónde se mostrará el botón de descarga (en la columna principal de Streamlit o en una columna específica), genera y muestra un botón de descarga para el archivo Excel.
# Usa st.markdown con unsafe_allow_html=True para insertar HTML (en este caso, el botón de descarga) en la aplicación Streamlit.
# El uso de unsafe_allow_html=True permite insertar etiquetas HTML directamente en la aplicación Streamlit, lo cual es necesario para implementar la funcionalidad del botón de descarga en este caso.

# -----------------------------------------------------


def download_button(object_to_download, download_filename, button_text, pickle_it=False):

    # Si pickle_it es True, intenta serializar el objeto con pickle.
    if pickle_it:
        try:
            object_to_download = pickle.dumps(object_to_download)
        except pickle.PicklingError as e:
            # Escribe el error en la aplicación Streamlit si hay un problema al hacer pickle.
            st.write(e)
            return None

    else:
        # Si el objeto es un objeto bytes, no hace nada.
        if isinstance(object_to_download, bytes):
            pass

        # Si el objeto es un DataFrame, lo convierte a CSV.
        elif isinstance(object_to_download, pd.DataFrame):
            object_to_download = object_to_download.to_csv(index=False)

        # Para cualquier otro tipo de objeto, intenta convertirlo a JSON.
        else:
            object_to_download = json.dumps(object_to_download)

    # Intenta codificar el objeto en base64.
    try:
        b64 = base64.b64encode(object_to_download.encode()).decode()

    except AttributeError as e:
        b64 = base64.b64encode(object_to_download).decode()

    # Genera un ID único para el botón.
    button_uuid = str(uuid.uuid4()).replace('-', '')
    button_id = re.sub('\d+', '', button_uuid)

    # Define el estilo CSS para el botón de descarga.
    custom_css = f""" 
        <style>
            ... (Estilos CSS para el botón) ...
        </style> """

    # Crea el enlace de descarga usando el objeto codificado en base64 y el estilo CSS.
    dl_link = custom_css + \
        f'<a download="{download_filename}" id="{button_id}" href="data:file/txt;base64,{b64}">{button_text}</a><br></br>'

    return dl_link

# La función realiza las siguientes acciones:

# Si pickle_it es True, intenta serializar el objeto proporcionado utilizando pickle.
# Si el objeto es un DataFrame de Pandas, lo convierte a formato CSV. Si es un objeto bytes, lo deja tal como está. Para cualquier otro tipo de objeto, intenta convertirlo a JSON.
# Codifica el objeto (ahora en formato de cadena o bytes) en formato base64, que es necesario para la descarga.
# Genera un ID único para el botón y define un estilo CSS personalizado para él.
# Crea un enlace de descarga (etiqueta <a>) que utiliza el objeto codificado en base64. Este enlace se presentará como un botón en la interfaz de usuario de Streamlit, gracias a los estilos CSS aplicados.
# Devuelve el código HTML del botón de descarga como una cadena de texto, que se puede usar con st.markdown en Streamlit para renderizar el botón en la aplicación.
# -----------------------------------------------------


def download_excel_torta(df_v, nombre='LogErrores', col=st):
    # Guarda el DataFrame 'df_v' como un archivo Excel.
    df_v.to_excel(nombre+'.xlsx', index=False)

    filename = nombre+'.xlsx'  # Define el nombre del archivo.
    # Abre el archivo en modo de lectura binaria.
    with open(filename, 'rb') as file:
        contents = file.read()  # Lee el contenido del archivo.

    # Crea un botón de descarga para el archivo y lo añade a la interfaz Streamlit.
    if col == st:
        download_button_str = download_button(contents, filename, nombre)
        st.markdown(download_button_str, unsafe_allow_html=True)
    else:
        download_button_str = download_button(contents, filename, nombre)
        col.markdown(download_button_str, unsafe_allow_html=True)

# Esta función convierte un DataFrame de Pandas a un archivo Excel y proporciona un botón de descarga en la aplicación Streamlit, ya sea en la página principal o en una columna específica.
# -----------------------------------------------------

# zzzzzzzzzzzzz,cols = [col11, col12, col13, col14,col15]}


def botones_descarga(Xf=None, variable='RangoConsumo', col=None):
    # Itera sobre cada categoría única en la columna especificada del DataFrame.
    for categoria in Xf[variable].unique():
        # Llama a 'download_excel_torta' para cada categoría.
        download_excel_torta(
            Xf[Xf[variable] == categoria], nombre=categoria, col=col)

# Esta función crea botones de descarga para segmentos específicos de un DataFrame, basándose en los valores únicos de una columna dada. Para cada valor único, genera un archivo Excel con los datos filtrados y proporciona un botón de descarga.
# -----------------------------------------------------


def download_txt(nombre, logs):
    # Define el nombre y la ruta del archivo de texto.
    archivo_txt = "archivo.txt"

    # Abre el archivo en modo escritura.
    with open(archivo_txt, "w") as archivo:
        # Escribe cada valor de la lista en el archivo.
        for valor in logs:
            archivo.write(valor + "\n \n")

    # Leer el contenido del archivo.
    with open(archivo_txt, 'rb') as file:
        contents = file.read()

    # Crea y muestra un botón de descarga para el archivo de texto.
    download_button_str = download_button(contents, archivo_txt, nombre)
    st.markdown(download_button_str, unsafe_allow_html=True)

    # st.download_button(nombre + '.txt', data=contents, file_name="archivo.txt")

# Esta función crea un archivo de texto con una lista de registros (logs), y luego proporciona un botón de descarga para este archivo en la aplicación Streamlit.

# En resumen, estas funciones facilitan la creación de archivos y su descarga desde una interfaz de Streamlit, permitiendo a los usuarios obtener datos en formatos útiles de manera eficiente y organizada.
# # -----------------------------------------------------


# Define una ruta en el servidor web que maneja las solicitudes GET a la raíz ('/').
@app.route('/', methods=['GET'])
def say_hello():
    # Importa el módulo 'request' de Flask para acceder a los detalles de la solicitud HTTP.
    from flask import request

    # Obtiene el valor de la cabecera 'X-Goog-IAP-JWT-Assertion' de la solicitud.
    # Esta cabecera típicamente contiene un JWT (JSON Web Token) cuando se usa en
    # entornos de Google Cloud con Identity-Aware Proxy (IAP) habilitado.
    assertion = request.headers.get('X-Goog-IAP-JWT-Assertion')

    # Valida el JWT y extrae el correo electrónico y el ID del usuario si el JWT es válido.
    # La función 'validate_assertion' debe estar definida en otro lugar del código.
    email, id = validate_assertion(assertion)

    # Construye una página HTML con un saludo personalizado que incluye el correo electrónico del usuario.
    page = "<h1>Hello {}</h1>".format(email)

    # Devuelve la página HTML como respuesta a la solicitud.
    return page

# En resumen, esta función realiza lo siguiente:

# Recupera un JWT de la cabecera 'X-Goog-IAP-JWT-Assertion' de la solicitud HTTP.
# Utiliza la función validate_assertion para validar este JWT. Si el JWT es válido, esta función devuelve el correo electrónico y el ID del usuario asociado con el JWT.
# Crea una página HTML simple que saluda al usuario utilizando su correo electrónico.
# Devuelve esta página HTML como la respuesta del servidor a la solicitud GET.
# Esta funcionalidad es particularmente útil en aplicaciones que están protegidas detrás de Google Cloud's Identity-Aware Proxy (IAP), donde cada solicitud incluye un JWT que autentica y autoriza al usuario.

# ------------------------------------------------------


def agregar_k(valor):
    return str(valor) + 'K'


def generar_graficos(df_t, configuraciones, mayus=True, color=1, auto_orden=False, total=False):
    """
    Genera gráficos de barras utilizando Altair y Streamlit.

    Parámetros:
    - df_t: DataFrame de pandas, el conjunto de datos.
    - configuraciones: Lista de diccionarios que contiene la configuración para cada gráfico.
    - mayus: Booleano, indica si se deben usar mayúsculas en las etiquetas del eje y.
    - color: Entero, código de color para el gráfico.
    - auto_orden: Booleano, indica si se debe reordenar automáticamente el DataFrame.
    - total: Booleano, indica si se deben mostrar los totales en el gráfico.

    Notas:
    - La función utiliza Altair para generar gráficos de barras y Streamlit para mostrarlos.
    - La configuración de cada gráfico se proporciona a través de la lista de diccionarios 'configuraciones'.
    - Se aplican transformaciones y ajustes al DataFrame antes de generar el gráfico.

    """
    for config in configuraciones:
        # Agrupar el DataFrame según la configuración
        df_group = df_t.groupby(by=config['groupby'], as_index=True)[
            'NIT9'].count()
        df_group = pd.DataFrame(df_group)

        if mayus == True:
            if not auto_orden:
                # Reordenar el DataFrame según el orden deseado
                df_group = df_group.reindex(config['order'])
            else:
                df_group.sort_values(by='NIT9', ascending=False, inplace=True)
        else:
            df_group.sort_values(by='NIT9', ascending=False, inplace=True)

        # Restablecer el índice
        df_group.reset_index(inplace=True, drop=False)
        df_group.dropna(inplace=True)
        df_group.reset_index(inplace=True, drop=True)

        # Renombrar columnas
        df_group.rename(
            {'NIT9': 'Cantidad_n', config['groupby']: config['y_axis']}, axis=1, inplace=True)
        df_group['Cantidad_n'] = pd.to_numeric(df_group['Cantidad_n'])
        df_group['Cantidad_n'] = df_group['Cantidad_n'] * 100

        if mayus == True:
            # Reemplazar etiquetas del eje y según el diccionario de configuración
            keys = config['order']
            values = config['order_f']
            diccionario = dict(zip(keys, values))
            df_group[config['y_axis']] = df_group[config['y_axis']
                                                  ].replace(diccionario)

        # Configurar la variable categórica en el eje y
        df_group[config['y_axis']] = pd.Categorical(
            df_group[config['y_axis']], ordered=True)

        # Calcular el porcentaje
        df_group['Porcentaje'] = df_group['Cantidad_n'] / \
            df_group['Cantidad_n'].sum() * 100
        df_group['Porcentaje'] = df_group['Porcentaje'].round(2)
        df_group['Porcentaje'] = df_group['Porcentaje'].apply(
            lambda x: ' {:.2f}%'.format(x))

        # Configurar colores según la opción seleccionada
        if color == 0:
            color_b = "#A6A6A6"
        elif color == 1:
            color_b = '#595959'
        elif color == 2:
            color_b = '#A6A6A6'
        elif color == 3:
            color_b = '#D9D9D9'
        elif color == 4:
            color_b = '#ffb617'
        elif color == 5:
            color_b = '#fef367'
        elif color == 6:
            color_b = '#ff6600'
        elif color == 7:
            color_b = '#66003d'

        # Configurar el gráfico de barras con Altair
        if mayus == True:
            if total == False:
                bar = alt.Chart(df_group).mark_bar().encode(
                    x=alt.X('Cantidad_n', axis=alt.Axis(
                        ticks=True, title=config['x_axis_title']
                    )),
                    y=alt.Y(config['y_axis'] + ":N", sort=list(df_group[config['y_axis']]),
                            axis=alt.Axis(ticks=False, title='')),
                    tooltip=[config['y_axis']+":N",
                             'Cantidad_n:Q', 'Porcentaje:O'],
                    text=alt.Text('Porcentaje:N')
                ).configure_mark(color=color_b).configure_view(fill="none").configure_axis(grid=False)

                # Mostrar el gráfico con Streamlit
                config['col'].altair_chart(
                    bar, use_container_width=True, theme="streamlit")
                st.write("")
            else:
                bar = alt.Chart(df_group).mark_bar().encode(
                    x=alt.X('Cantidad', axis=alt.Axis(
                        ticks=False, title=config['x_axis_title'])),
                    y=alt.Y(config['y_axis'] + ":N", sort=list(df_group[config['y_axis']]),
                            axis=alt.Axis(ticks=False, title='')),
                    tooltip=[config['y_axis']+":N",
                             'Cantidad:Q', 'Porcentaje:O'],
                    text=alt.Text('Porcentaje:N')
                ).configure_mark(color=color_b).configure_view(fill="none").configure_axis(grid=False).configure_axisX(ticks=False, labels=False)

                # Mostrar el gráfico con Streamlit
                config['col'].altair_chart(
                    bar, use_container_width=True, theme="streamlit")
                st.write("")

        else:
            bar = alt.Chart(df_group).mark_bar().encode(
                x=alt.X('Cantidad', axis=alt.Axis(
                    ticks=False, title=config['x_axis_title'])),
                y=alt.Y(config['y_axis'] + ":N", sort=list(df_group[config['y_axis']]),
                        axis=alt.Axis(ticks=False, title=None)),
                tooltip=[config['y_axis']+":N", 'Cantidad:Q', 'Porcentaje:O'],
                text=alt.Text('Porcentaje:N')
            ).configure_mark(color=color_b).configure_view(fill="none").configure_axis(grid=False)

            # Mostrar el gráfico con Streamlit
            config['col'].altair_chart(
                bar, use_container_width=True, theme="streamlit")
            st.write("")

            """Esta función utiliza Altair para generar gráficos de barras y Streamlit para mostrarlos. Permite personalizar varios aspectos del gráfico, como la agrupación de datos, el orden, la orientación de las etiquetas, los colores y más. Puedes ajustar los parámetros según tus necesidades específicas."""

# ------------------------------------------------------


def convert_df(df):
    # IMPORTANT: Cache the conversion to prevent computation on every rerun
    return df.to_excel()  # .encode('utf-8')


def dona_plotly(df_prob_prod, producto='INSTALACIONES', col=None, titulo=None, tamano_pantalla=(400, 400)):
    """
    Genera un gráfico de dona (donut chart) con Plotly a partir de un DataFrame de probabilidades de productos.

    Parámetros:
    - df_prob_prod: DataFrame de pandas, contiene las probabilidades de productos.
    - producto: Cadena, nombre del producto para el cual se genera el gráfico.
    - col: No utilizado en la función, parece ser un parámetro no utilizado actualmente.
    - titulo: Cadena, título del gráfico.
    - tamano_pantalla: Tupla, tamaño de la pantalla del gráfico en píxeles.

    Notas:
    - El gráfico de dona representa las probabilidades de 'Alta', 'Media' y 'Baja'.
    - Los colores y el formato del gráfico están personalizados.
    - El título del gráfico, si se proporciona, se muestra en la parte superior.
    - La función utiliza la biblioteca Plotly para la creación del gráfico.
    """
    # Obtener valores, etiquetas y colores
    valores = df_prob_prod.loc[:, producto].astype(int) * 100
    etiquetas = ['Alta', 'Media', 'Baja']
    colores = ['#595959', '#A6A6A6', '#f4f4f4']

    total = sum(valores)
    conteos = [str(valor) for valor in valores]
    porcentajes = [f'{(valor/total)*100:.1f}%' for valor in valores]

    # Crear el gráfico de dona con Plotly
    fig = go.Figure(data=[
        go.Pie(
            labels=etiquetas,
            values=valores,
            hole=0.55,
            textinfo='none',  # 'label+text+percent',
            hovertemplate='%{label}',  # '%{label}<br>%{text} (%{percent})',
            marker=dict(colors=colores)
        )
    ])

    # Actualizar el diseño del gráfico
    if titulo:
        fig.update_layout(title={
            'text': titulo,
            'y': 0.95,
            'yanchor': 'top',
            'font': {'size': 20, 'family': "Roboto, serif", 'color': '#595959'}
        })

    fig.update_layout(width=tamano_pantalla[0], height=tamano_pantalla[1])
    fig.update_layout(showlegend=False)  # Ocultar la leyenda

    # Actualizar las trazas para mostrar información adicional
    fig.update_traces(
        text=conteos,
        textinfo='label+text+percent',  # Activa el texto personalizado
        textposition='outside'  # Mueve el texto fuera de la dona
    )
    # La función dona_plotly utiliza la biblioteca Plotly para crear un gráfico de dona (donut chart) a partir de un DataFrame de probabilidades de
    # productos.

# -----------------------------------------------------

    # Reducir el tamaño de las etiquetas
    fig.update_traces(
        textfont=dict(
            size=13  # Tamaño de la fuente de las etiquetas
        )
    )

# -----------------------------------------------------

    col.plotly_chart(fig, use_container_width=True)
    # Encabezado inicial
    # header = st.empty()


def espacio(col, n):
    if n > 0:
        for i in range(n):
            col.write('')


# -----------------------------------------------------

def scatter_plot(df, col=None):
    """
    Genera un gráfico de dispersión personalizado con Plotly Express.

    Parámetros:
    - df: DataFrame de pandas, contiene los datos para el gráfico.
    - col: Objeto de Streamlit, se utiliza para mostrar el gráfico en la aplicación Streamlit.

    Notas:
    - El gráfico de dispersión utiliza colores y tamaños condicionales basados en columnas específicas del DataFrame.
    - Se utiliza una paleta de color personalizada y una escala de color continua.
    - El gráfico se personaliza en términos de diseño y etiquetas.
    - La función utiliza Plotly Express para la creación del gráfico.

    """
    # Definir los colores base
    color_azul = 'rgb(70, 30, 125)'
    color_amarillo = 'rgb(254, 243, 103)'

    # Crear la paleta de color
    colores = [color_azul, color_amarillo]

    # Crear la escala de color continua
    colorscale = colors_plotly.make_colorscale(colores)

    # Crear el gráfico scatter utilizando Plotly Express
    fig = px.scatter(df, x='DEPARTAMENTO', y='ACTIVIDADES',
                     color='OPORTUNIDADESVENDIDAS', size='OPORTUNIDADESCOTIZADAS($)',
                     color_continuous_scale=colorscale
                     )

    # Personalizar el diseño del gráfico
    fig.update_layout(coloraxis_colorbar=dict(len=1, ypad=0))
    fig.update_layout(xaxis_title='Departamento', yaxis_title='Actividad económica',
                      coloraxis_colorbar=dict(title='Ventas'), width=875, height=500)

    fig.update_layout(coloraxis_colorbar=dict(
        tickmode='array',  # Usar modo de ticks de arreglo
        tickvals=list(range(0, 27, 2)),  # Valores de los ticks personalizados
        ticktext=list(range(0, 27, 2))  # Etiquetas de los ticks personalizados
    ))

    # Actualizar las trazas para personalizar la información del hover
    fig.update_traces(
        hovertemplate='<b>Departamento</b>: %{x}<br>'
        '<b>Actividad económica</b>: %{y}<br>'
        '<b>Oportunidades vendidas</b>: %{marker.color}<br>'
        '<b>Oportunidades cotizadas</b>: %{marker.size:,}<extra></extra>'
    )

    # Mostrar el gráfico con Streamlit
    col.plotly_chart(fig, use_container_width=True)

    # Agregar un espacio en blanco después del gráfico
    col.write('')

    """La función scatter_plot utiliza Plotly Express para crear un gráfico de dispersión (scatter plot) personalizado con colores y tamaños condicionales.
    """

# -----------------------------------------------------


# Bloque 1: Configuración inicial y estilos

def main():
    """
    Configuración inicial de la aplicación y estilos.
    """

    # Configura título e ícono de página
    st.set_page_config(page_title="scotiabankcolpatria",
                       page_icon="img/Icono.png", layout="wide")

    # Lee el contenido del archivo CSS
    css = open('styles.css', 'r').read()

    # Agrega estilo personalizado
    st.markdown(f'<style>{css}</style>', unsafe_allow_html=True)

    # Variable que controla la visibilidad de la imagen
    b = False

    # Crea pestañas ("tabs") con nombres "Reporte descriptivo" y "Resultado modelo"
    vista2, vista1 = st.tabs(["Reporte descriptivo", "Resultado modelo"])

    # Menú y logo en la barra lateral
    st.sidebar.image("img/logo.png", width=245)
    st.sidebar.write("")

    # Establece el estilo del botón cuando se realiza un hover
    st.markdown("""
            <style>
            div.stButton > button:hover {
                background-color:#f0f2f6;
                color:#461e7d
            }
            </style>""", unsafe_allow_html=True)

    # Código HTML para enlaces a redes sociales con iconos
    st.markdown(
        """
        <head>
            <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/5.15.3/css/all.min.css">
        </head>

        <div style="display: flex; justify-content: center;">
            <a href="https://www.facebook.com/ScotiabankColpatria/?locale=es_LA" style="color: #1877F2; margin: 0 30px;">
                <i class="fab fa-facebook" style="font-size: 30px;"></i>
            </a>
            <a href="https://www.instagram.com/scotiabankcolpatria/?hl=es" style="color: #E4405F; margin: 0 30px;">
                <i class="fab fa-instagram" style="font-size: 30px;"></i>
            </a>
            <a href="https://twitter.com/ScotiaColpatria/status/1559630139490803713" style="color: #1DA1F2; margin: 0 30px;">
                <i class="fab fa-twitter-square" style="font-size: 30px;"></i>
            </a>
            <a href="https://www.youtube.com/channel/UC7ii5Ew1qdz47rn4CntnYnA" style="color: #FF0000; margin: 0 30px;">
                <i class="fab fa-youtube-square" style="font-size: 30px;"></i>
            </a>
            <a href="https://co.linkedin.com/company/scotiabankcolpatria" style="color: #1877F2; margin: 0 30px;">
                <i class="fab fa-linkedin" style="font-size: 30px;"></i>
            </a>
        </div>
    """,
        unsafe_allow_html=True
    )

    # Este bloque se encarga de la configuración inicial de la aplicación y la presentación de estilos, incluyendo la configuración de la página, la lectura de un archivo CSS, y la #creación de pestañas, menú lateral y enlaces a redes sociales con iconos.

# -----------------------------------------------------

    # Bloque 2: Sección de carga de archivos y procesamiento del modelo para múltiples clientes

    with st.sidebar.expander("MODELO MÚLTIPLES CLIENTES", expanded=False):
        """
        Sección dedicada al modelo de múltiples clientes.
        """

        try:
            # Cargar archivos en formato xlsx
            datos = st.file_uploader("Subir archivos: ", type=["xlsx"])

            if datos is not None:
                # Leer el archivo Excel y asignar índices
                dataframe = pd.read_excel(datos)
                dataframe.index = range(1, len(dataframe)+1)

                try:
                    # Convertir la columna 'FECHACONSTITUCION' a formato datetime si es posible
                    dataframe['FECHACONSTITUCION'] = dataframe['FECHACONSTITUCION'].astype(
                        'datetime64[ns]')
                except:
                    pass

                # Validar el archivo
                original_len = len(dataframe.copy())
                ob = validar_preprocesar_predecir_organizarrtados.Modelos_2(
                    dataframe)
                df_v, text, final_flag = ob.Validar_todo()

                # En este bloque, se presenta la sección dedicada al modelo de múltiples clientes. El código utiliza la función st.sidebar.expander para crear #un expander (expandible) en la barra lateral que contiene la funcionalidad del modelo de múltiples clientes. Permite al usuario cargar #archivos en formato xlsx mediante st.file_uploader, leer el archivo Excel, y realizar algunas operaciones como la conversión de la columna #'FECHACONSTITUCION' a formato datetime. Luego, se realiza la validación del archivo utilizando un objeto de la clase Modelos_2 del módulo #validar_preprocesar_predecir_organizarrtados.


# -----------------------------------------------------

# Bloque 3: Validación y ejecución del modelo para múltiples clientes

                if final_flag == False:

                    # Si la validación del modelo de múltiples clientes indica problemas, se muestra la información de los registros aptos
                    # y se permite al usuario ejecutar el modelo si lo desea.

                    logs, logs_riesgo, indices_posibles = ob.Logs()

                    if '1' not in logs_riesgo:
                        tx_registros_aptos = str('Registros aptos para recomendar: ') + str(len(
                            indices_posibles)/10) + 'K (' + str(round(100*(len(indices_posibles))/original_len, 2)) + '%)'
                        st.success(tx_registros_aptos, icon="✅")
                        b = st.button("Ejecutar Modelo", type="primary")

                    download_txt(logs=logs, nombre='Log_errores')

                    for i, j in zip(range(len(logs)), logs_riesgo):
                        if i == 0:
                            # Si es el primer log agrega '¡Ups! Parece que hay un problema.'
                            if j == '1':
                                st.write(
                                    '<div align="center"><h2>¡Ups! Parece que hay un problema.</h2></div>', unsafe_allow_html=True)

                            if (len(logs[i]) > 150) & (j == '1'):
                                st.warning(logs[i][:172]+'...', icon="⚠️")
                            elif (len(logs[i]) > 150) & (j == 0):
                                st.info(logs[i][:172]+'...', icon="ℹ️")
                            elif (len(logs[i]) <= 150) & (j == '1'):
                                st.warning(logs[i][:], icon="⚠️")
                            elif (len(logs[i]) <= 150) & (j == 0):
                                st.info(logs[i][:], icon="ℹ️")
                        else:
                            if (len(logs[i]) > 150) & (j == '1'):
                                st.warning(logs[i][:172]+'...', icon="⚠️")
                            elif ((len(logs[i]) > 150) & (j == 0)):
                                st.info(logs[i][:172]+'...', icon="ℹ️")
                            elif ((len(logs[i]) <= 150) & (j == '1')):
                                st.warning(logs[i], icon="⚠️")
                            elif ((len(logs[i]) <= 150) & (j == 0)):
                                st.info(logs[i], icon="ℹ️")

                    st.write('')

                else:
                    st.success(text+' (100%)', icon="✅")
                    b = st.button("Ejecutar Modelo", type="primary")

        except UnboundLocalError:
            st.warning('Error. Problemas con características del archivo.')


# Bloque 4: Ejecución del modelo y visualización de resultados

    if b == True:
        with vista1:    # Modelo Múltiples Clientes
            try:
                Xi, Xf = ob.predict_proba()

                # Modifico nombres de categorías
                keys = ['SINCATALOGAR', 'MENORA5000',
                        'ENTRE5000Y10000', 'ENTRE10000Y55000',  'MAYORA55000']
                values = ['Sin catalogar', 'Menor a 5000 kW⋅h',
                          'Entre 5000 y 10000 kW⋅h', 'Entre 10000 y 55000 kW⋅h']
                dic_rango_consumo = dict(zip(keys, values))

                Xf['RANGOCONSUMO'] = Xf['RANGOCONSUMO'].replace(
                    dic_rango_consumo)

                hm_df = pd.DataFrame({'index': ['INSTALACIONES', 'MANTENIMIENTO', 'ESTUDIOS', 'AUMENTOS_CARGA', 'FIBRA_OPTICA',
                                                'REDESELECTRICAS', 'ILUMINACION', 'CUENTASNUEVAS']})

                productos = ['Producto_1', 'Producto_2',
                             'Producto_3']  # Solo 3 primeras

                for i in productos:
                    hm_df = pd.merge(hm_df, pd.DataFrame(Xf[i].value_counts(dropna=False)).reset_index(drop=False),
                                     how='outer', on='index')

                # Suma # primeras predicciones
                df_tmp = pd.DataFrame(hm_df['index'].copy())
                df_tmp.rename({'index': 'Productos'}, axis=1, inplace=True)

                df_tmp['Top 3'] = hm_df[['Producto_1',
                                         'Producto_2', 'Producto_3']].sum(axis=1)
                df_tmp['Porcentaje'] = df_tmp['Top 3'] / \
                    df_tmp['Top 3'].sum() * 100
                df_tmp['Porcentaje'] = df_tmp['Porcentaje'].round(2)

                keys = ['INSTALACIONES', 'MANTENIMIENTO', 'ESTUDIOS', 'AUMENTOS_CARGA',
                        'FIBRA_OPTICA', 'REDESELECTRICAS', 'ILUMINACION', 'CUENTASNUEVAS']
                values = ['INSTALACIONES', 'MANTENIMIENTO', 'ESTUDIOS', 'AUMENTOS DE CARGA',
                          'FIBRA OPTICA', 'REDES ELECTRICAS', 'ILUMINACION', 'CUENTAS NUEVAS']
                diccionario = dict(zip(keys, values))

                df_tmp['Productos'] = df_tmp['Productos'].replace(
                    diccionario)  # Corrijo nombre de los productos

                # Obtener la paleta de colores 'Purples'
                colors = plt.cm.Purples(range(256))
                # Seleccionar los tres tonos deseados
                C = [colors[80], colors[170], colors[255]]

                merged_df = pd.DataFrame(index=['Alta', 'Media', 'Baja'])
                df_prob_prod = pd.DataFrame()

                productos = ['INSTALACIONES', 'MANTENIMIENTO', 'ESTUDIOS', 'AUMENTOS_CARGA',
                             'FIBRA_OPTICA', 'REDESELECTRICAS', 'ILUMINACION', 'CUENTASNUEVAS']

                for prod in productos:

                    df_tmp1 = pd.DataFrame(
                        Xf[Xf['Producto_1'] == prod]['Probabilidad_1'].value_counts())
                    df_tmp2 = pd.DataFrame(
                        Xf[Xf['Producto_2'] == prod]['Probabilidad_2'].value_counts())
                    df_tmp3 = pd.DataFrame(
                        Xf[Xf['Producto_3'] == prod]['Probabilidad_3'].value_counts())

                    merged_df = pd.DataFrame(index=['Alta', 'Media', 'Baja'])

                    merged_df = merged_df.merge(
                        df_tmp1, left_index=True, right_index=True, how='outer')
                    merged_df = merged_df.merge(
                        df_tmp2, left_index=True, right_index=True, how='outer')
                    merged_df = merged_df.merge(
                        df_tmp3, left_index=True, right_index=True, how='outer')

                    merged_df = merged_df.fillna(0)
                    merged_df['Total'] = merged_df.sum(axis=1)
                    df_prob_prod[prod] = merged_df['Total']

                df_prob_prod = df_prob_prod.reindex(['Alta', 'Media', 'Baja'])

                for prod in productos:
                    df_prob_prod['P_'+prod] = np.round(
                        df_prob_prod[prod]/df_prob_prod[prod].sum() * 100, 2)

                container0 = st.container()
                container0.markdown(
                    """
                    <style>
                    .custom-container {
                        background-color: #A6A6A6;
                        padding: 2.5px;
                    }
                    </style>
                    """,
                    unsafe_allow_html=True
                )
                container0.markdown(
                    f'<div class="custom-container"></div>', unsafe_allow_html=True)

                # Crear el primer contenedor
                container1 = st.container()
                # Aplicar CSS personalizado al contenedor
                container1.markdown(
                    """
                    <style>
                    .custom-container {
                        background-color: #f2f0f7;
                        padding: 2.5px;
                    }
                    </style>
                    """,
                    unsafe_allow_html=True
                )

                # Crear el segundo contenedor
                container2 = st.container()
                # Dividir el primer contenedor en dos columnas
                col1_container1, col2_container1, col3_container1 = container1.columns(spec=[
                                                                                       2.5, 2.3, 1])
                # Dividir el segundo contenedor en tres columnas
                col1_container2, col2_container2 = container2.columns(
                    2)  # , col3_container2, col4_container2

                # En este bloque, se realiza la ejecución del modelo y la visualización de los resultados. Se obtienen las predicciones del modelo y se #realiza un procesamiento de los datos para presentar la información de manera clara y comprensible. Se crean contenedores y se aplica CSS #personalizado para mejorar la presentación visual de la información en la interfaz de usuario.

# -----------------------------------------------------

# Bloque 5: Visualización detallada de resultados y gráficos

                # Títulos y colores configurables
                tamaño1 = 30  # Tamaño1 del título
                tamaño2 = 60  # Tamaño2 del título
                color1 = '#595959'  # Color del título en formato hexadecimal
                color2 = '#A6A6A6'

                # Añadir espacio al contenedor
                container1.markdown(
                    f'<div class="custom-container"></div>', unsafe_allow_html=True)

                # Añadir títulos al contenedor
                col1_container1.markdown(
                    f'<h1 style="text-align: center; font-size: {tamaño1}px; color: {color1};">Total clientes analizados</h1>', unsafe_allow_html=True)

                col1_container1.markdown(
                    f'<h1 style="text-align: center; font-size: {tamaño2}px; color: {color2}">{str("  "+str(len(Xf)/10)+" K")}</h1>', unsafe_allow_html=True)

                # Configuraciones para generar gráficos
                configuraciones = [
                    {
                        'groupby': 'Producto_1',
                        'count_col': 'NIT9',
                        'x_axis_title': None,
                        'y_axis': 'Producto 1',
                        'col': col2_container1,
                        'order': ['INSTALACIONES', 'MANTENIMIENTO', 'ESTUDIOS', 'AUMENTOS_CARGA', 'FIBRA_OPTICA', 'REDESELECTRICAS', 'ILUMINACION', 'CUENTASNUEVAS'],
                        'order_f': ['TC One Rewards Gold', 'TC Visa Avianca LifeMiles', 'Seguro Tarjeta Protegida', 'Seguro de Desempleo', 'Asistencia Mascotas', 'Seguro de Vida', 'Asistencia Integral', 'Seguro Auto']
                    }
                ]

                # Añadir espacio y generar gráficos en el contenedor
                espacio(col2_container1, 1)
                generar_graficos(
                    Xf, auto_orden=True, configuraciones=configuraciones, color=0, total=False)
                espacio(col3_container1, 9)

                # Filtrar y descargar datos específicos
                Xf = Xf.loc[:, ['NIT9', 'Producto_1', 'Probabilidad_1', 'Valor_probabilidad1', 'Producto_2', 'Probabilidad_2', 'Valor_probabilidad2', 'Producto_3', 'Probabilidad_3', 'Valor_probabilidad3',
                                'Producto_4', 'Probabilidad_4', 'Valor_probabilidad4', 'Producto_5', 'Probabilidad_5', 'Valor_probabilidad5', 'Producto_6', 'Probabilidad_6', 'Valor_probabilidad6', 'Producto_7',
                                'Probabilidad_7', 'Valor_probabilidad7', 'Producto_8', 'Probabilidad_8', 'Valor_probabilidad8']]

                # Mapear nombres de productos
                dic1 = ['INSTALACIONES', 'MANTENIMIENTO', 'ESTUDIOS', 'AUMENTOS_CARGA',
                        'FIBRA_OPTICA', 'REDESELECTRICAS', 'ILUMINACION', 'CUENTASNUEVAS']
                dic2 = ['TC One Rewards Gold', 'TC Visa Avianca LifeMiles', 'Seguro Tarjeta Protegida',
                        'Seguro de Desempleo', 'Asistencia Mascotas', 'Seguro de Vida', 'Asistencia Integral', 'Seguro Auto']
                Xf = Xf.replace(dict(zip(dic1, dic2)))
                download_excel(Xf, 'Resultado', col=col2_container1)

                # Visualización de gráficos de dona
                dona_plotly(df_prob_prod=df_prob_prod, producto='INSTALACIONES',
                            titulo='TC One Rewards Gold', col=col1_container2)
                dona_plotly(df_prob_prod=df_prob_prod, producto='MANTENIMIENTO',
                            titulo='Seguro Tarjeta Protegida', col=col2_container2)
                dona_plotly(df_prob_prod=df_prob_prod, producto='ESTUDIOS',
                            titulo='TC Visa Avianca LifeMiles', col=col1_container2)
                dona_plotly(df_prob_prod=df_prob_prod, producto='AUMENTOS_CARGA',
                            titulo='Asistencia Mascotas', col=col2_container2)
                dona_plotly(df_prob_prod=df_prob_prod, producto='FIBRA_OPTICA',
                            titulo='Seguro de Desempleo', col=col1_container2)
                dona_plotly(df_prob_prod=df_prob_prod, producto='REDESELECTRICAS',
                            titulo='AP Travel', col=col2_container2)
                dona_plotly(df_prob_prod=df_prob_prod, producto='ILUMINACION',
                            titulo='Asistencia Integral', col=col1_container2)
                dona_plotly(df_prob_prod=df_prob_prod, producto='CUENTASNUEVAS',
                            titulo='Seguro Auto', col=col2_container2)

                # Manejar excepción si se intenta ejecutar sin cargar archivo
            except UnboundLocalError:
                st.warning(
                    'Error. En el menú de la izquierda, cargar archivo en la sección "Modelo múltiples clientes"')

                """Este bloque se encarga de la visualización detallada de los resultados y la creación de gráficos específicos para cada producto. Los títulos y colores son configurables, y se utiliza un contenedor para organizar y presentar la información de manera ordenada. Además, se maneja una excepción para informar al usuario si intenta ejecutar sin cargar un archivo previamente.
                """

# -----------------------------------------------------

        with vista2:  # Descriptiva
            try:
                # Crear pestañas para diferentes visualizaciones
                tab4, tab2 = st.tabs(["Demográfico", "Ventas"])

                # Transformar y cargar datos para las visualizaciones
                df_t, _ = ob.transform_load()
                df_t = df_t.copy()

                # Visualizaciones en la pestaña "Ventas"
                with tab2:
                    st.write("")
                    st.write("")
                    col1, col2, col3 = st.columns(spec=[1, 5, 1])

                    # Configuraciones de los gráficos para la sección "Clientes con producto"
                    configuraciones = [
                        {
                            'groupby': 'RANGODECOMPRA($)',
                            'count_col': 'NIT9',
                            'x_axis_title': 'Cantidad de clientes',
                            'y_axis': 'Rango de compra',
                            'col': col2,
                            'order': ['SINCATALOGAR', 'NOCOMPRADOR', 'PEQUENOCOMPRADOR', 'MEDIANOCOMPRADOR', 'GRANCOMPRADOR', 'COMPRADORMEGAPROYECTOS'],
                            'order_f': ['TC One Rewards Gold', 'TC One Rewards Gold', 'Seguro Tarjeta Protegida', 'Seguro de Desempleo', 'Asistencia Mascotas', 'Asistencia Hogar', 'No comprador']
                        }]
                    generar_graficos(df_t, configuraciones, color=1)

                    # Configuraciones de los gráficos para la sección "Oferta último semestre"
                    configuraciones = [
                        {
                            'groupby': 'RANGORECURRENCIACOMPRA',
                            'count_col': 'NIT9',
                            'x_axis_title': 'Cantidad de clientes',
                            'y_axis': 'Recurrencia de compra',
                            'col': col2,
                            'order': ['SINCATALOGAR', 'NOCOMPRADOR', 'UNICACOMPRA', 'BAJARECURRENCIA', 'RECURRENCIAMEDIA', 'GRANRECURRENCIA'],
                            'order_f': ['Sin catalogar', 'TC One Rewards Gold', 'Seguro Tarjeta Protegida', 'Seguro de Desempleo', 'Asistencia Mascotas', 'Asistencia Hogar']
                        }]
                    generar_graficos(df_t, configuraciones, color=2)

                    col2.subheader("Frecuencia de contacto")
                    configuraciones = [
                        {
                            'groupby': 'TIPOCLIENTE#OPORTUNIDADES',
                            'count_col': 'NIT9',
                            'x_axis_title': 'Cantidad de clientes',
                            'y_axis': 'Tipo de cliente por número de oportunidades',
                            'col': col2,
                            'order': ['SINCATALOGAR', 'NICOMPRA-NICOTIZA', 'SOLOCOTIZAN', 'COTIZANMASDELOQUECOMPRAN',
                                      'COMPRANYCOTIZAN', 'COMPRANMASDELOQUECOTIZAN', 'SIEMPRECOMPRAN'],
                            'order_f': ['Mayores a 180 días', 'Entre a 151 y 180 días', 'Entre 121 y 150 días', 'Entre 91 y 120 días', 'Entre 61 y 90 días', 'Entre 31 y 60 días', 'Sin catalogar']
                        }]
                    generar_graficos(df_t, configuraciones, color=3)

                    # col2.subheader("Valor de prima")
                    # configuraciones = [
                    #     {
                    #         'groupby': 'TIPOCLIENTE$OPORTUNIDADES',
                    #         'count_col': 'NIT9',
                    #         'x_axis_title': 'Cantidad de clientes',
                    #         'y_axis': 'Tipo de cliente por valor de oportunidades',
                    #         # 'chart_title': 'Gráfico 4 TIPOCLIENTE$OPORTUNIDADES',
                    #         'col': col2,
                    #         'order': ['SINCATALOGAR', 'NICOMPRA-NICOTIZA', 'SOLOCOTIZAN', 'COTIZANMASDELOQUECOMPRAN',
                    #                   'COMPRANYCOTIZAN', 'COMPRANMASDELOQUECOTIZAN', 'SIEMPRECOMPRAN'],
                    #         'order_f': ['Sin catalogar', 'Menos a 40 mil', 'Entre 40 mil y 60 mil', 'Entre 60 mil y 80 mil',
                    #                     'Entre 80 mil y 100 mil', 'Entre 100 mil y 120 mil', 'Mayor a 120 mil']   # Orden deseado de las categorías
                    #     }]
                    # generar_graficos(df_t, configuraciones, color=4)

                with tab4:  # Sección Demográfica y de Ventas
                    st.write("")
                    st.write("")

                    col31, col32, col33 = st.columns(spec=[1, 5, 1])

                    # Agrupar actividades por la actividad principal (EMIS)
                    df_c = ob.Agrupar_actividades('ACTIVIDADPRINCIPAL(EMIS)')

                    # Configuraciones para el gráfico de pastel (Generación digital)
                    configuraciones = [
                        {
                            'groupby': 'ACTIVIDADES',
                            'count_col': 'NIT9',
                            'x_axis_title': 'Cantidad de clientes',
                            'y_axis': 'Sector económico',
                            'col': col32,
                            'order': ['SERVICIOS', 'AGROPECUARIO', 'INDUSTRIAL', 'TRANSPORTE', 'COMERCIO', 'FINANCIERO', 'CONSTRUCCION', 'ENERGETICO', 'COMUNICACIONES'],
                            'order_f': ['Generación Baby Boomers', 'Millennials',  'Generación Z', 'Transporte', 'Generación X', 'Generación Baby boomers', 'Construcción', 'Energético', 'Comunicaciones']
                        }
                    ]

                    col32.subheader("Generación digital")

                    # Generar y mostrar el gráfico de pastel en Plotly
                    col32.plotly_chart(ob.generar_graficos_pie(
                        configuraciones, paleta=1, width=500, height=300), use_container_width=True)

                    # with tab4:: Sección dedicada a la información demográfica y de ventas.
                    # col31, col32, col33 = st.columns(spec=[1, 5, 1]): Se dividen las columnas para la disposición del contenido.
                    # df_c = ob.Agrupar_actividades('ACTIVIDADPRINCIPAL(EMIS)'): Se agrupa el DataFrame por la actividad principal (EMIS).
                    # configuraciones: Configuración para el gráfico de pastel relacionado con la generación digital.
                    # col32.plotly_chart(...): Se muestra el gráfico de pastel utilizando Plotly en la columna col32.

                    # -------------------------------------------

                    # Configuraciones de los gráficos de barras
                    configuraciones = [
                        {
                            'groupby': 'TAMANOEMPRESA',
                            'count_col': 'NIT9',
                            'x_axis_title': 'Cantidad de clientes',
                            'y_axis': 'Tamaño de la empresa',
                            'col': col32,
                            'order': ['SINCATALOGAR', 'PEQUENAEMPRESA', 'MEDIANAEMPRESA', 'GRANEMPRESA'],
                            'order_f': ['Sin catalogar', 'Profesional', 'Tecnólogo', 'Bachiller']
                        },
                        {
                            'groupby': 'CATEGORIZACIONSECTORES',
                            'count_col': 'NIT9',
                            'x_axis_title': 'Cantidad de clientes',
                            'y_axis': 'Categoría del sector',
                            'col': col32,
                            'order': ['SINCATALOGAR', 'OTROSSECTORES', 'SECTORALTOVALOR'],
                            'order_f': ['Sin catalogar', 'Empleado', 'Independiente']
                        },
                        {
                            'groupby': 'ESTATUSOPERACIONAL',
                            'count_col': 'NIT9',
                            'x_axis_title': 'Cantidad de clientes',
                            'y_axis': 'Estatus operacional',
                            'col': col32,
                            'order': ['NOSECONOCEELESTATUS', 'BAJOINVESTIGACIONLEGAL', 'OPERACIONAL'],
                            'order_f': ['No se conoce el estatus', 'Bajo investigación legal',  'Operacional']
                        }
                    ]

                    col32.subheader("Nivel educativo")
                    # Generar gráficos de barras para nivel educativo
                    generar_graficos(df_c, configuraciones[0:1], color=3)

                    col32.subheader("Situación laboral")
                    # Generar gráficos de barras para situación laboral
                    generar_graficos(df_c, configuraciones[1:2], color=4)

                    # Sección Demográfica
                    st.write("")
                    st.write("")

                    col000, col0, col002, col003 = st.columns(
                        spec=[0.35, 5, 1, 0.25])

                    # Configuraciones de los gráficos demográficos
                    configuraciones = [
                        {
                            'groupby': 'CATEGORIADEPARTAMENTO',
                            'count_col': 'NIT9',
                            'x_axis_title': 'Cantidad de clientes',
                            'y_axis': 'Categoría de departamento',
                            'col': col0,
                            'order': ['NOSECONOCEELDEPARTAMENTO', 'OTROSDEPARTAMENTOS', 'COSTA', 'CUNDINAMARCA', 'BOGOTADC'],
                            'order_f': ['No se conoce el departamento',  'Otros departamentos',  'Costa',  'Cundinamarca',  'Bogotá DC']
                        }
                    ]

                    # Manejo de UnboundLocalError si no se ha cargado un archivo
            except UnboundLocalError:
                st.warning(
                    'No ha cargado un archivo para procesar. En el menú de la izquierda, cargue un archivo en la sección Modelo Múltiples Variables')


if __name__ == '__main__':
    main()
