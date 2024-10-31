import pandas as pd
from django.core.management.base import BaseCommand
from django.db import transaction
from topeducation.models import *

class Command(BaseCommand):
    help = 'Importar cursos desde un archivo Excel y asignar imágenes a las plataformas y universidades'

    def assign_university_image(self, university_name):
        university_images = {
            'Universidad de Palermo': 'assets/Universidades/Universidad-de-Palermo.png',
            'Pontificia Universidad Catolica de Chile': 'assets/Universidades/Pontificia-Universidad-Catolica-de-Chile.png',
            'SAE-MÉXICO': 'assets/Universidades/SAE-México.png',
            'Universidad Anáhuac': 'assets/Universidades/Universidades-Anáhuac.png',
            'Berklee College of Music': 'assets/Universidades/Berklee-College-of-Music.png',
            'Universitat de Barcelona': 'assets/Universidades/Universitat-Autònoma-de-Barcelona.png',
            'Universidad Autónoma de Barcelona': 'assets/Universidades/Universitat-Autònoma-de-Barcelona.png',
            'Yad Vashem': 'assets/Universidades/Yad-Vashem.png',
            'Universidad de los Andes': 'assets/Universidades/Universidad-de-los-Andes.png',
            'Universidad Nacional Autónoma de Mexico': 'assets/Universidades/UNAM.png',
            'Universidad Austral': 'assets/Universidades/Universidad-Austral.png',
            'University of New Mexico': 'assets/Universidades/University-of-New-Mexico.png',
            'Macquarie University': 'assets/Universidades/Macquarie-University.png',
            'University of Michigan': 'assets/Universidades/University-of-Michigan.png',
            'University of Virginia': 'assets/Universidades/University-of-Virginia.png',
            'Banco Interamericano de Desarrollo': 'assets/Universidades/Banco-Interamericano-de-Desarrollo.png',
            'Duke University': 'assets/Universidades/Duke-University.png',
            'Northwestern University': 'assets/Universidades/Northwestern-University.png',
            'Museum of Modern Art': 'assets/Universidades/Museum-of-Modern-Art.png',
            'Parsons School of Design, The New School': 'assets/Universidades/Parsons-School-of-Design,-The-New-School.png',
            'University of Colorado Boulder': 'assets/Universidades/University-of-Colorado-Boulder.png',
            'University of Illinois Urbana-Champaign': 'assets/Universidades/University-of-Illinois-Urbana-Champaign.png',
            'Tecnológico de Monterrey': 'assets/Universidades/Tecnológico-de-Monterrey.png',
            'The-Chinese-University-of-Hong-Kong': 'assets/Universidades/The-Chinese-University-of-Hong-Kong.png',
            'The University of North Carolina at Chapel Hill': 'assets/Universidades/The-University-of-North-Carolina-at-Chapel-Hill.png',
            'California Institute of Arts': 'assets/Universidades/Calarts.png',
            'Pontificia Universidad Católica del Perú': 'assets/Universidades/Pontificia-Universidad-Católica-del-Perú.png',
            'Pontificia Universidad Catolica de Chile': 'assets/Universidades/Pontificia-Universidad-Católica-de-Chile.png',
            'Wesleyan University': 'assets/Universidades/Wesleyan-University.png',
            'University of California, Irvine': 'assets/Universidades/University-of-California,-Irvine.png',
            'IE Business School': 'assets/Universidades/IE-Business-School.png'
        }
        return university_images.get(university_name)

    def assign_platform_image(self, platform_name):
        platform_images = {
            'edX': 'assets/Plataformas/Edx Mini logo.svg',
            'Coursera': 'assets/Plataformas/Coursera mini logo.svg',
            'MasterClass': 'assets/Plataformas/MasterClass logo mini.svg',
        }
        return platform_images.get(platform_name)
    
    def assign_enterprise_image(self, enterprise_name):
        enterprise_images = {
            'Capitals Coalition': 'assets/Empresas/nonx',
            'DeepLearning.AI': 'assets/Empresas/DeepLearning.AI.png',
            'Big Interview': 'assets/Empresas/Big-Interview.png',
            'UBITS': 'assets/Empresas/UBITS.png',
            'HubSpot Academy': 'assets/Empresas/hubspot-academy.png',
            'SV Academy': 'assets/Empresas/SV-Academy.png',
            'Pathstream': 'assets/Empresas/Pathstream.png',
            'SalesForce': 'assets/Empresas/Salesforce.png',
            'The Museum of Modern Art': 'assets/Empresas/Museum-of-Modern-Art.png',
            'Banco Interamericano de Desarrollo': '',
            'Yad Vashem': 'assets/Empresas/Yad-Vashem.png',
            'Salesforce, SV Academy': 'assets/Empresas/Salesforce-SV-Academy.png'
        }
        return enterprise_images.get(enterprise_name)
    
    def get_or_create_topic(self, topic_id, topic_name):
        try: 
            return Temas.objects.get(id=topic_id)
        except Temas.DoesNotExist:
            try:
                return Temas.objects.get(topic_name=topic_name)
            except Temas.DoesNotExist:
                return Temas.objects.create(id=topic_id, topic_name=topic_name)

    def handle(self, *args, **kwargs):
        # Lee el archivo Excel
        excel_path = "C:\\Users\\felip\\Documents\\TOPEDUCATIONMICROSERVICES\\backend-django\\topeducation\\management\\commands\\test89.xlsx"
        
        # Imprimir información de depuración
        df = pd.read_excel(excel_path, skiprows=1, nrows= 301)
        print("Columnas en el DataFrame:")
        for col in df.columns:
            print(f"- {col}")
        
        print("\nPrimeras filas del DataFrame:")
        print(df.head())
        
        # Recorre las filas del archivo y crea los cursos
        for index, row in df.iterrows():
            try:
                with transaction.atomic():
                    # Debug de cada fila
                    print(f"\nProcesando fila {index + 2}:")
                    print(f"Tema (id): {row.get('Tema (id)', 'NO ENCONTRADO')}")
                    print(f"Título: {row.get('Titulo', 'NO ENCONTRADO')}")
                    
                    # Obtener el tema de la certificación
                    topic_id = row['Tema (id)']
                    if pd.isna(topic_id):
                        print(f"Tema (id) es NaN en la fila {index + 2}")
                        continue
                    
                    topic_name = row.get('Tema', f'Tema {topic_id}')
                    certification_topic = self.get_or_create_topic(int(topic_id), topic_name)
                    
                    # Obtener o crear la plataforma y asignar la imagen
                    platform_id = row['Proveedor de curso']
                    certification_platform = Plataformas.objects.get(id=platform_id)
                    platform_name = certification_platform.nombre
                    platform_img = self.assign_platform_image(platform_name)
                    
                    
                    
                    enterprise_id = row['EMPRESA']
                    if enterprise_id == 0:
                        certification_enterprise = None
                        enterprise_name = None
                    else:
                        certification_enterprise = Empresas.objects.get(id=enterprise_id)
                        enterprise_name = certification_enterprise.nombre
                    
                    enterprise_image = self.assign_enterprise_image(enterprise_name)
                    #certification_enterprise = Empresas.objects.get(id=enterprise_id)
                    #enterprise_name = certification_enterprise.nombre
                    #nterprise_img = self.assign_enterprise_image(enterprise_name)

                    # Obtener o crear la universidad y asignar la imagen
                    university_id = row['Universidad']
                    if university_id == 0:
                        certification_university = None
                        university_name = None
                    else:
                        certification_university = Universidades.objects.get(id=university_id)
                        university_name = certification_university.nombre

                    university_image = self.assign_university_image(university_name)
                    
                    region_id = row['REGION UNIVERSIDAD']
                    certification_region = None if region_id == 0 else Regiones.objects.get(id=region_id)
                    
                    enterprise_id = row['EMPRESA']
                    certification_enterprise = None if enterprise_id == 0 else Empresas.objects.get(id=enterprise_id)
                    
                    # Crear la certificación
                    Certificaciones.objects.create(
                        nombre=row['Titulo'],
                        tema_certificacion=certification_topic,
                        palabra_clave_certificacion=row['KW'],
                        plataforma_certificacion=certification_platform,
                        url_certificacion_original=row['Link'],
                        metadescripcion_certificacion=row['Meta D'],
                        instructores_certificacion=row['Instructor/es'],
                        nivel_certificacion=row['Nivel'],
                        tiempo_certificacion =row['Horario'],
                        lenguaje_certificacion=row['Idioma'],
                        aprendizaje_certificacion=row['¿Qué aprenderás?'],
                        habilidades_certificacion =row['Habilidades que obtendrás'],
                        experiencia_certificacion= row['Adquiere experiencia en la materia de tu interés\n'],
                        contenido_certificacion = row['Contenido'],
                        modulos_certificacion=row['Modulos'],
                        testimonios_certificacion=row['Testimonios'],
                        universidad_certificacion=certification_university,
                        empresa_certificacion=row['EMPRESA'],
                        region_universidad_certificacion=certification_region,
                        url_imagen_universidad_certificacion=university_image,
                        url_imagen_plataforma_certificacion=platform_img,
                        url_imagen_empresa_certificacion = enterprise_image,
                        imagen_final = university_image if university_image else enterprise_image
                    )
                    print(f"✓ Curso importado exitosamente: {row['Titulo']}")
            
            except KeyError as e:
                print(f"Error de columna en fila {index + 2}: {str(e)}")
                print("Columnas disponibles:", df.columns.tolist())
            except Exception as e:
                print(f"Error al procesar fila {index + 2}: {str(e)}")
                print(f"Datos de la fila:")
                print(row)

        print('Proceso de importación completado')
        
