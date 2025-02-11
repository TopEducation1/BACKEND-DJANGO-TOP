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
        contenido_html = """<h1>Tipos de estrategias de aprendizaje y cómo aplicarlas</h1>
    <p>Las estrategias de aprendizaje juegan un papel fundamental en el proceso de adquisición de conocimiento y habilidades. Desde los métodos más tradicionales hasta las innovaciones más recientes, existen una variedad de enfoques que pueden adaptarse a las necesidades individuales de cada aprendiz.</p>
    <p>En este artículo, exploraremos diversos tipos de estrategias de aprendizaje y examinaremos cómo pueden ser aplicadas de manera efectiva para potenciar el desarrollo académico, profesional y personal.</p>
    <img src="/assets/Piezas/tipos_de_estrategias_de_aprendizaje_y_como_aplicarlas_miniatura.png" alt="Miniatura estrategias de aprendizaje">
    
    <h2>¿Qué son las estrategias de aprendizaje?</h2>
    <p>Las estrategias de aprendizaje son métodos o procesos utilizados por los estudiantes para adquirir, comprender y retener información de manera más efectiva. Van más allá de la simple memorización, abarcando técnicas como la organización de la información, la elaboración de conexiones significativas y el monitoreo del propio proceso de aprendizaje.</p>
    <p>Comprender y aplicar estrategias de aprendizaje efectivas es fundamental, ya que no solo facilitan el proceso de adquisición de conocimientos, sino que también promueven una comprensión más profunda y duradera de los temas.</p>
    <p>Además, estas estrategias empoderan a los estudiantes al proporcionarles herramientas prácticas para enfrentar desafíos académicos y desarrollar habilidades de aprendizaje autónomo.</p>
    <p><a href="#" target="_blank">Quizás te interese leer: Estrategias de aprendizaje para diferentes tipos de estudiantes</a></p>
    
    <h2>Tipos de estrategias de aprendizaje</h2>
    
    <h3>Estrategias cognitivas</h3>
    <p>Las estrategias cognitivas son aquellas que implican la manipulación activa del material de aprendizaje, como el resumen, la elaboración y la organización de la información.</p>
    <ul>
        <li>Elaboración: Crear analogías o relacionar el nuevo material con conocimientos previos.</li>
        <li>Organización: Creación de mapas conceptuales o esquemas.</li>
        <li>Herramientas útiles: MindMeister, XMind, Quizlet.</li>
    </ul>
    
    <h3>Estrategias metacognitivas</h3>
    <p>Estas estrategias se enfocan en el proceso mismo de aprendizaje, con actividades como la autoevaluación, la planificación y el monitoreo del progreso.</p>
    <ul>
        <li>Diarios de aprendizaje y toma de notas: Evernote, OneNote.</li>
        <li>Organización del tiempo: Trello, Todoist.</li>
    </ul>
    
    <h3>Estrategias motivacionales</h3>
    <p>Estas estrategias trabajan en el ámbito emocional y motivacional del aprendizaje.</p>
    <ul>
        <li>Establecimiento de metas: GoalsOnTrack, Habitica.</li>
        <li>Uso de recompensas y autoafirmaciones: ThinkUp.</li>
    </ul>
    
    <p><a href="#" target="_blank">Quizás te interese leer: Consejos, herramientas y tecnologías para el aprendizaje autónomo</a></p>
    
    <h2>Cómo aplicar las estrategias de aprendizaje</h2>
    
    <h3>Cursos en Línea</h3>
    <p>Explorar cursos en línea es una forma efectiva de ampliar habilidades y conocimientos.</p>
    <ul>
        <li>Plataformas recomendadas: Coursera, edX, Masterclass.</li>
        <li>Curso destacado: "Learning How to Learn" en Coursera.</li>
    </ul>
    <p>¿Sabías que con Top Education puedes acceder a todo el contenido de Coursera, edX y Masterclass en un solo lugar y con una única membresía?</p>
    <p><strong>Prueba Top Education 👇</strong></p>
    
    <h3>Recursos Personalizados</h3>
    <p>Selecciona recursos según tu estilo de aprendizaje.</p>
    <ul>
        <li>Visual: Mapas mentales y esquemas.</li>
        <li>Auditivo: Audiolibros y podcasts.</li>
    </ul>
    <p><a href="#" target="_blank">Quizás te interese leer: Cómo aumentar el salario por medio de educación virtual</a></p>
    
    <img src="/assets/Piezas/tipos_de_estrategias_de_aprendizaje_y_como_aplicarlas_vertical.png" alt="Estrategias de aprendizaje vertical">
    
    <h3>Comunidad y Colaboración</h3>
    <p>Unirse a comunidades en línea y participar en grupos de estudio puede proporcionar apoyo adicional.</p>
    <ul>
        <li>Foros de discusión y grupos de estudio: Discord, Reddit.</li>
        <li>Webinars y talleres colaborativos.</li>
    </ul>
    
    <h2>Conclusión</h2>
    <p>Comprender los diferentes tipos de estrategias de aprendizaje y cómo aplicarlas puede mejorar el proceso de adquisición de conocimientos y habilidades.</p>
    <p>Al ser conscientes de estas estrategias y cultivarlas de manera reflexiva, podemos potenciar nuestro aprendizaje y alcanzar un mayor éxito académico y profesional.</p>
    <p>Estrategias para aprender online</p>
"""

        row = next(ws.iter_rows(min_row=3, max_row=3))
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