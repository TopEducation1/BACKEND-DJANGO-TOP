import pandas as pd
from django.core.management.base import BaseCommand
from django.db import transaction
from topeducation.models import *
import os


class Command(BaseCommand):
    help = 'Importar cursos desde un archivo Excel con nuevo formato de columnas'

    def assign_platform_image(self, platform_name):
        platform_images = {
            'edX': 'assets/Plataformas/Edx Mini logo.png',
            'Coursera': 'assets/Plataformas/Coursera mini logo.png',
            'MasterClass': 'assets/Plataformas/MasterClass logo mini.svg',
        }
        return platform_images.get(platform_name)
    
    def get_or_create_skill(self, skill_id, skill_title):
        try: 
            return Habilidades.objects.get(id=skill_id)
        except Habilidades.DoesNotExist:
            try:
                return Habilidades.objects.get(nombre=skill_title)
            except Habilidades.DoesNotExist:
                return Habilidades.objects.create(id=skill_id, nombre=skill_title)
    
    def get_or_create_topic(self, topic_id, topic_name):
        try: 
            return Temas.objects.get(id=topic_id)
        except Temas.DoesNotExist:
            try:
                return Temas.objects.get(nombre=topic_name)
            except Temas.DoesNotExist:
                return Temas.objects.create(id=topic_id, nombre=topic_name)

    def handle(self, *args, **kwargs):
        current_dir = os.path.dirname(os.path.abspath(__file__))
        excel_path = os.path.join(current_dir, "test89.xlsx")
        
        df = pd.read_excel(excel_path, skiprows=1)
        df.columns = df.columns.str.strip()
        
        print("Columnas en el DataFrame después de limpiar:")
        for col in df.columns:
            print(f"- {col}")
        
        for index, row in df.iterrows():
            try:
                with transaction.atomic():
                    print(f"\nProcesando fila {index + 2}:")
                    
                    # Obtener el tema de la certificación
                    topic_id = row['Habilidad (id)']
                    if pd.isna(topic_id):
                        print(f"Tema (id) es NaN en la fila {index + 2}")
                        continue
                    
                    topic_name = row.get('Tema', f'Tema {topic_id}')
                    certification_topic = self.get_or_create_topic(int(topic_id), topic_name)
                    
                    skill_id = row['Habilidad (id)']
                    if pd.isna(skill_id):
                        print(f"Habilidad (id) es NaN en la fila {index + 2}")
                        continue
                    
                    skill_title = row['Título']
                    certification_skill = self.get_or_create_skill(int(skill_id), skill_title)
                    
                    platform_id = row['Proveedor de curso']
                    certification_platform = Plataformas.objects.get(id=platform_id)
                    platform_name = certification_platform.nombre
                    platform_img = self.assign_platform_image(platform_name)
                    
                    # Combinar la descripción del instructor y el nombre del instructor
                    descripcion_instructor = f"{row['Descripción']} - {row['Instructor(a)']}"
                    
                    # Crear la certificación con los campos correctos del modelo
                    Certificaciones.objects.create(
                        nombre=row['Titulo'],
                        palabra_clave_certificacion=row['KW'],
                        metadescripcion_certificacion=row['Meta D'],
                        url_certificacion_original=row['URL'],
                        plataforma_certificacion=certification_platform,
                        tiempo_certificacion=row['Duración de la clase'],
                        aprendizaje_certificacion=row['Lo que aprenderás'],
                        contenido_certificacion=row['Lecciones'],
                        nivel_certificacion="NONE",  # Campo por defecto si es necesario
                        lenguaje_certificacion="NONE",  # Campo por defecto si es necesario
                        experiencia_certificacion=row["Acerca de esta clase"],  # Campo por defecto si es necesario
                        modulos_certificacion="NONE",  # Campo por defecto si es necesario
                        testimonios_certificacion=descripcion_instructor,  # Usamos este campo para la descripción del instructor
                        url_imagen_plataforma_certificacion=platform_img,
                        tema_certificacion_id = certification_topic.id,
                        url_imagen_universidad_certificacion = row['Imagen'],
                        video_certificacion = row['Link video'] 
                        
                    )
                    print(f"✓ Curso importado exitosamente: {row['Titulo']}")
            
            except KeyError as e:
                print(f"Error de columna en fila {index + 2}: {str(e)}")
                print("Datos de la fila:")
                print(row)
            except Exception as e:
                print(f"Error al procesar fila {index + 2}: {str(e)}")
                print("Datos de la fila:")
                print(row)

        print('Proceso de importación completado')