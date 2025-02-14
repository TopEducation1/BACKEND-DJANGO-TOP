import os
from openpyxl import load_workbook
from django.core.management.base import BaseCommand
from django.utils.text import slugify
from django.contrib.auth import get_user_model
from topeducation.models import Blog, CategoriaBlog, Autor

User = get_user_model()

class Command(BaseCommand):
    help = 'Importa blogs desde Excel con contenido HTML formateado'

    def handle(self, *args, **options):
        excel_path = "C:/Users/felip/Desktop/Top Education Archivo Maestro 2025.xlsx"
        
        try:
            wb = load_workbook(excel_path)
            ws = wb.active
            column_mapping = {cell.value.strip(): idx for idx, cell in enumerate(ws[1], start=0) if cell.value}
            print(column_mapping)
            
            required_columns = ["Titulo", "Meta descripción", "Palabra clave", "Autor", "Categoría", "Objetivo", "Miniatura"]
            for col in required_columns:
                if col not in column_mapping:
                    self.stdout.write(self.style.ERROR(f'❌ Columna faltante: {col}'))
                    return

        except Exception as e:
            self.stdout.write(self.style.ERROR(f'❌ Error cargando Excel: {str(e)}'))
            return

        # Contenido HTML formateado (el que está arriba)
        contenido_html = """<h1>edX vs. Coursera ¿Cuál plataforma educativa es mejor?</h1>

<p>En los últimos años, las plataformas educativas en línea se han vuelto indispensables para el aprendizaje a distancia, y dos de las más destacadas son edX y Coursera. Ambas plataformas colaboran con universidades y organizaciones de prestigio para ofrecer una amplia gama de cursos y programas educativos. Desde habilidades técnicas hasta humanidades, edX y Coursera han transformado el acceso al conocimiento a nivel global, permitiendo a millones de personas mejorar sus competencias profesionales y personales.</p>

<p>Este artículo ofrece una comparación objetiva entre las características de edX vs Coursera. Se exploran aspectos como la variedad de cursos, los métodos de aprendizaje, y los beneficios que cada plataforma presenta. Con esta información, podrás evaluar cuál opción se ajusta mejor a sus necesidades y metas educativas, sin una conclusión que favorezca a una plataforma sobre la otra.</p>

<img src="/assets/Piezas/edx_vs_coursera_cual_plataforma_educativa_es_mejor_miniatura.png" alt="edX vs Coursera">

<h2>Origen de edX</h2>

<p>edX es una plataforma educativa en línea fundada en 2012 por el MIT y la Universidad de Harvard, con el objetivo de hacer accesible la educación de calidad a nivel global. Actualmente, cuenta con más de 45 millones de estudiantes y ofrece cursos gratuitos y de pago en áreas como tecnología, negocios y ciencias. Los certificados de cursos varían entre $50 y $300 USD, mientras que los programas avanzados, como micromásters y grados completos, tienen costos más altos.</p>

<h3>Principales características de edX</h3>

<p>edX destaca por sus cursos autoguiados, que permiten a los estudiantes avanzar a su propio ritmo. Ofrece certificaciones verificadas para aquellos que deseen validar sus conocimientos, además de programas de grado en áreas como tecnología, ciencias, negocios y más. La plataforma es conocida por su enfoque en la educación superior, con contenido de alta calidad proveniente de universidades y organizaciones líderes.</p>

<p>Para más información, visita <a href="https://www.edx.org" target="_blank">edx.org</a>.</p>

<h2>Origen de Coursera</h2>

<p>Coursera es una plataforma educativa en línea fundada en 2012 por profesores de la Universidad de Stanford con el objetivo de democratizar la educación de calidad. Colabora con más de 275 universidades y empresas líderes como Google e IBM, ofreciendo cursos gratuitos y de pago en diversas áreas. Cuenta con más de 124 millones de usuarios, y los precios para certificaciones varían entre $39 y $79 USD al mes, con programas de grado que tienen precios más elevados.</p>

<h3>Principales características de Coursera</h3>

<p>Coursera ofrece cursos especializados en diversas disciplinas, con la posibilidad de obtener certificaciones, así como acceder a programas de licenciatura y maestría. Una de sus principales ventajas es la flexibilidad de aprendizaje, ya que los estudiantes pueden elegir entre cursos autoguiados o con fechas límite, adaptándose a su propio ritmo y disponibilidad. Además, sus alianzas con instituciones y empresas aseguran un contenido actualizado y relevante.</p>

<p>Para más información, visita <a href="https://www.coursera.org" target="_blank">coursera.org</a>.</p>

<div class="cta">
    <a href="https://info.top.education/es-mx/como-encontrar-trabajo-con-poca-experiencia" target="_blank">Cómo encontrar trabajo con poca experiencia</a>
</div>

<h2>edX vs. Coursera: Métodos de aprendizaje</h2>

<p>Tanto edX como Coursera ofrecen un alto nivel de flexibilidad, permitiendo a los usuarios aprender a su propio ritmo. Ambas plataformas cuentan con cursos autoguiados y la posibilidad de elegir entre varios programas de estudio, aunque Coursera ofrece más opciones con fechas de inicio programadas y plazos definidos. edX, por su parte, tiende a enfocarse más en el autoaprendizaje con menos restricciones de tiempo. En cuanto a certificaciones, Coursera ofrece programas con proyectos prácticos, mientras que edX se enfoca más en evaluaciones académicas tradicionales.</p>

<span>Quizás te interese leer: <a href="#" target="_blank">Estas son las 3 mejores páginas de e-learning</a></span>

<h2>Variedad de cursos y programas disponibles</h2>

<p>Tanto edX como Coursera ofrecen una amplia gama de cursos, pero con enfoques diferentes. edX tiene más de 4,000 cursos centrados en tecnología, ciencias y humanidades, con un fuerte enfoque en programas universitarios y grados completos. Coursera, con más de 7,000 cursos, combina contenido académico y profesional, colaborando con empresas como Google e IBM, y se especializa en certificaciones valoradas en el mercado laboral.</p>

<h2>¿Cuál plataforma es mejor para ti?</h2>

<p>No existe una respuesta única sobre cuál es la mejor plataforma entre edX y Coursera, ya que esto depende de los intereses y objetivos de cada persona. Por ejemplo, si buscas un enfoque académico profundo con grados completos, edX puede ser la mejor opción. En cambio, Coursera podría ser más adecuada para quienes buscan certificaciones profesionales o aprender habilidades específicas que son demandadas en el mundo empresarial. Cada plataforma ofrece beneficios distintos, dependiendo de lo que el usuario necesite.</p>

<img src="/assets/Piezas/edx_vs_coursera_cual_plataforma_educativa_es_mejor_vertical.png" alt="edX vs Coursera">

<h2>Consejos para elegir entre edX y Coursera</h2>

<ul>
    <li><strong>Investiga las instituciones asociadas:</strong> Si valoras estudiar cursos respaldados por universidades de renombre, revisa qué instituciones están asociadas con los programas que te interesan. edX tiende a colaborar con universidades tradicionales, mientras que Coursera se asocia con empresas líderes.</li>
    <li><strong>Explora la oferta de programas:</strong> Si planeas realizar un programa completo como un máster o especialización, revisa cuál de las plataformas ofrece un programa más alineado con tus intereses y el nivel de profundidad que buscas.</li>
    <li><strong>Accesibilidad y comunidad:</strong> Considera qué plataforma te ofrece una mejor experiencia de usuario. Coursera tiene una comunidad más activa con foros y proyectos colaborativos, mientras que edX puede tener una experiencia más académica y estructurada.</li>
    <li><strong>Opiniones de los usuarios:</strong> Revisa las opiniones y reseñas de otros usuarios en cada plataforma. Coursera, al estar más orientada a habilidades prácticas y empleabilidad, suele recibir comentarios positivos por la aplicabilidad de sus cursos. En edX, los estudiantes valoran la calidad académica de los cursos y la profundidad de los contenidos.</li>
</ul>

<span>Quizás te interese leer: <a href="#" target="_blank">Cómo elegir el proveedor de educación en línea para su empresa, consejos, tips y más</a></span>

<img src="/assets/Piezas/edx_vs_coursera_cual_plataforma_educativa_es_mejor_tabla.png" alt="edX vs Coursera">

<h2>Accede a lo mejor de edX y Coursera en Top Education</h2>

<p>En Top Education tienes la oportunidad de acceder fácilmente a los cursos más destacados tanto de edX como de Coursera, todo desde una sola plataforma. Esto te permite explorar una amplia variedad de contenido educativo impartido por dos de las plataformas líderes en el mundo de la formación online. Podrás encontrar cursos diseñados para cubrir todo tipo de áreas de conocimiento, desde habilidades técnicas hasta desarrollo personal, adaptados a tus intereses y necesidades.</p>

<p>Además, al contar con las mejores opciones de aprendizaje en un solo lugar, tendrás la oportunidad de mejorar tus competencias y avanzar tanto en tu desarrollo profesional como en el personal. No pierdas la ocasión de aprovechar estos recursos educativos de calidad mundial y darle un impulso a tu carrera.</p>

<div class="cta">
    <a href="https://info.top.education/es-mx/como-encontrar-trabajo-con-poca-experiencia" target="_blank">Cómo encontrar trabajo con poca experiencia</a>
</div>
"""

        row = next(ws.iter_rows(min_row=2, max_row=2))
        try:
            blog_data = self.obtener_datos_fila(row, column_mapping)
            if blog_data['titulo']:
                self.guardar_blog(blog_data, contenido_html, 3)
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'❌ Error procesando blog: {str(e)}'))

        self.stdout.write(self.style.SUCCESS('\n✅ Proceso completado'))

    def obtener_datos_fila(self, row, column_mapping):
        return {
            'titulo': row[column_mapping["Titulo"]].value or '',
            'meta_desc': row[column_mapping["Meta descripción"]].value or '',
            'palabra_clave': row[column_mapping["Palabra clave"]].value or '',
            'autor': row[column_mapping["Autor"]].value or '',
            'categoria': row[column_mapping["Categoría"]].value or 'General',
            'objetivo': row[column_mapping["Objetivo"]].value or '',
            'miniatura': row[column_mapping["Miniatura"]].value or ''
        }

    def guardar_blog(self, data, contenido, idx):
        try:
            
            counter = 1
            
    

            categoria, _ = CategoriaBlog.objects.get_or_create(nombre_categoria_blog=data['categoria'])
            autor = Autor.objects.filter(nombre_autor=data['autor']).first() or User.objects.first()
            #print(data['Miniatura'])

            Blog.objects.create(
                nombre_blog=data['titulo'],
                metadescripcion_blog=data['meta_desc'],
                palabra_clave_blog=data['palabra_clave'],
                autor_blog=autor,
                categoria_blog=categoria,
                objetivo_blog=data['objetivo'],
                contenido=contenido,
                miniatura_blog = data['miniatura']
            )

            self.stdout.write(self.style.SUCCESS(f"✅ Blog guardado - {data['titulo']}"))

        except Exception as e:
            self.stdout.write(self.style.ERROR(f'❌ Error guardando blog: {str(e)}'))