import sys
import os
from bs4 import BeautifulSoup, NavigableString
from django.core.management.base import BaseCommand
from django.utils.text import slugify
from topeducation.models import Blog
import re

class Command(BaseCommand):
    help = 'Importa blogs desde HTML como un único documento'

    def add_arguments(self, parser):
        parser.add_argument('file_path', type=str, help='Ruta del archivo HTML')

    def process_list(self, list_element, level=0):
        """Procesa listas anidadas manteniendo la jerarquía"""
        items = []
        indent = "  " * level
        
        for li in list_element.find_all('li', recursive=False):
            text = ' '.join(self.process_element(li))
            items.append(f"{indent}- {text}")
                
        return items

    def process_element(self, element):
        """Procesa elementos HTML preservando formato y estructura"""
        if element is None:
            return []
            
        content = []
        
        for child in element.children:
            if isinstance(child, NavigableString):
                text = child.strip()
                if text:
                    content.append(text)
            elif child.name in ['strong', 'b']:
                inner_text = ' '.join(self.process_element(child))
                content.append(f"**{inner_text}**")
            elif child.name in ['span', 'div', 'p']:
                inner_content = self.process_element(child)
                if inner_content:
                    content.extend(inner_content)

        return content

    def handle(self, *args, **kwargs):
        file_path = kwargs['file_path']
        
        if not os.path.exists(file_path):
            self.stderr.write(self.style.ERROR(f'🚨 Error: El archivo {file_path} no existe'))
            return

        try:
            self.stdout.write(self.style.SUCCESS(f'Iniciando procesamiento del archivo: {file_path}'))
            
            with open(file_path, 'r', encoding='utf-8') as file:
                content = file.read()
                self.stdout.write('Archivo leído correctamente')
                
                soup = BeautifulSoup(content, 'html.parser')
                self.stdout.write('HTML parseado correctamente')

                # Usar el primer H2 como título del blog
                first_h2 = soup.find('h2')
                if not first_h2:
                    self.stderr.write(self.style.WARNING('No se encontró título H2 en el documento'))
                    return

                titulo_blog = "Requisitos de Visas de Estudiante - Multidestinos"
                self.stdout.write(f'Título del blog: {titulo_blog}')

                # Procesar todo el contenido como un solo documento
                content = []
                
                # Procesar todos los elementos del documento
                for element in soup.find_all(['h2', 'h3', 'h4', 'p', 'ul', 'ol']):
                    if element.name.startswith('h'):
                        # Agregar encabezados con el nivel correcto de #
                        level = int(element.name[1])
                        text = element.get_text(strip=True)
                        content.append(f"\n{'#' * level} {text}\n")
                    elif element.name == 'p':
                        text = ' '.join(self.process_element(element))
                        if text.strip():
                            content.append(f"\n{text}\n")
                    elif element.name in ['ul', 'ol']:
                        list_items = self.process_list(element)
                        if list_items:
                            content.append("\n" + "\n".join(list_items) + "\n")

                # Crear el blog
                if content:
                    contenido_blog = '\n'.join(content).strip()
                    
                    # Crear slug único
                    base_slug = slugify(titulo_blog)[:490]
                    slug = base_slug
                    counter = 1
                    
                    while Blog.objects.filter(slug=slug).exists():
                        slug = f"{base_slug}-{counter}"
                        counter += 1

                    Blog.objects.create(
                        titulo_blog=titulo_blog,
                        contenido_blog=contenido_blog,
                        slug=slug
                    )
                    
                    self.stdout.write(
                        self.style.SUCCESS(f'✅ Blog creado: "{titulo_blog}" (slug: {slug})')
                    )
                else:
                    self.stdout.write(
                        self.style.WARNING('⚠️ No se encontró contenido para el blog')
                    )

        except Exception as e:
            self.stderr.write(
                self.style.ERROR(f'🚨 Error general: {str(e)}')
            )

        self.stdout.write(self.style.SUCCESS('Proceso completado'))