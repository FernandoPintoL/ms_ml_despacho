"""
Exploratory Data Analysis (EDA) - Fase 2
Analiza datos y genera visualizaciones para entender patrones
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
import pyodbc
from datetime import datetime
import logging
from typing import Tuple

logger = logging.getLogger(__name__)

# Configurar estilo de seaborn
sns.set_style("whitegrid")
plt.rcParams['figure.figsize'] = (12, 6)


class ExploratoryAnalysis:
    """Realiza análisis exploratorio de datos para ML"""

    def __init__(self, server: str, database: str, username: str, password: str):
        """
        Inicializar análisis

        Args:
            server: Servidor SQL Server
            database: Nombre de BD
            username: Usuario
            password: Contraseña
        """
        self.server = server
        self.database = database
        self.username = username
        self.password = password
        self.connection = None
        self.df = None

    def connect(self) -> bool:
        """Establecer conexión a BD"""
        try:
            connection_string = (
                f'DRIVER={{ODBC Driver 17 for SQL Server}};'
                f'SERVER={self.server};'
                f'DATABASE={self.database};'
                f'UID={self.username};'
                f'PWD={self.password}'
            )
            self.connection = pyodbc.connect(connection_string, timeout=10)
            logger.info(f"Conectado a {self.database}")
            return True
        except Exception as e:
            logger.error(f"Error conectando: {e}")
            return False

    def load_data(self) -> bool:
        """Cargar datos desde BD"""
        if not self.connection:
            if not self.connect():
                return False

        try:
            query = """
            SELECT
                dispatch_id, severity_level, hour_of_day, day_of_week, is_weekend,
                available_ambulances_count, nearest_ambulance_distance_km,
                paramedics_available_count, nurses_available_count,
                active_dispatches_count, ambulances_busy_percentage,
                average_response_time_minutes, actual_response_time_minutes,
                actual_travel_distance_km, optimization_score,
                paramedic_satisfaction_rating, patient_satisfaction_rating,
                was_optimal
            FROM ml.assignment_history
            ORDER BY dispatch_id
            """

            self.df = pd.read_sql(query, self.connection)
            logger.info(f"Cargados {len(self.df)} registros")
            return True

        except Exception as e:
            logger.error(f"Error cargando datos: {e}")
            return False

    def disconnect(self):
        """Cerrar conexión"""
        if self.connection:
            self.connection.close()

    def get_basic_stats(self) -> dict:
        """Obtener estadísticas básicas"""
        if self.df is None:
            return {}

        stats = {
            'total_records': len(self.df),
            'columns': len(self.df.columns),
            'null_counts': self.df.isnull().sum().to_dict(),
            'optimal_count': (self.df['was_optimal'] == 1).sum(),
            'optimal_rate': (self.df['was_optimal'] == 1).sum() / len(self.df) * 100,
            'numeric_summary': self.df.describe().to_dict(),
            'dtypes': self.df.dtypes.to_dict()
        }
        return stats

    def print_basic_stats(self):
        """Imprimir estadísticas básicas"""
        if self.df is None:
            print("No data loaded")
            return

        print("\n" + "=" * 70)
        print("ESTADISTICAS BASICAS")
        print("=" * 70)
        print(f"Total de registros: {len(self.df)}")
        print(f"Total de columnas: {len(self.df.columns)}")
        print(f"\nRegistros optimos: {(self.df['was_optimal'] == 1).sum()}")
        print(f"Registros no optimos: {(self.df['was_optimal'] == 0).sum()}")
        print(f"Tasa de optimalidad: {(self.df['was_optimal'] == 1).sum() / len(self.df) * 100:.2f}%")

        print("\n" + "-" * 70)
        print("VALORES NULOS")
        print("-" * 70)
        null_counts = self.df.isnull().sum()
        if null_counts.sum() > 0:
            print(null_counts[null_counts > 0])
        else:
            print("Sin valores nulos")

        print("\n" + "-" * 70)
        print("ESTADISTICAS NUMERICAS")
        print("-" * 70)
        print(self.df.describe())

    def plot_target_distribution(self):
        """Gráfico de distribución del target"""
        if self.df is None:
            return

        fig, axes = plt.subplots(1, 2, figsize=(12, 4))

        # Distribución de was_optimal
        self.df['was_optimal'].value_counts().plot(kind='bar', ax=axes[0], color=['#e74c3c', '#2ecc71'])
        axes[0].set_title('Distribución de was_optimal')
        axes[0].set_xlabel('Optimal')
        axes[0].set_ylabel('Cantidad')
        axes[0].set_xticklabels(['No Optimal (0)', 'Optimal (1)'], rotation=0)

        # Porcentaje
        self.df['was_optimal'].value_counts().apply(lambda x: x / len(self.df) * 100).plot(
            kind='pie', ax=axes[1], autopct='%1.1f%%', colors=['#e74c3c', '#2ecc71']
        )
        axes[1].set_title('Porcentaje de Optimalidad')
        axes[1].set_ylabel('')

        plt.tight_layout()
        plt.savefig('notebooks/01_target_distribution.png', dpi=300, bbox_inches='tight')
        plt.close()
        logger.info("Gráfico saved: 01_target_distribution.png")

    def plot_severity_distribution(self):
        """Gráfico de distribución por severidad"""
        if self.df is None:
            return

        fig, axes = plt.subplots(1, 2, figsize=(12, 4))

        # Distribución de severidad
        self.df['severity_level'].value_counts().sort_index().plot(kind='bar', ax=axes[0], color='skyblue')
        axes[0].set_title('Distribución de Severidad')
        axes[0].set_xlabel('Severity Level')
        axes[0].set_ylabel('Cantidad')

        # Severidad vs Optimalidad
        severity_optimal = self.df.groupby('severity_level')['was_optimal'].agg(['sum', 'count'])
        severity_optimal['rate'] = severity_optimal['sum'] / severity_optimal['count'] * 100
        severity_optimal['rate'].plot(kind='bar', ax=axes[1], color='coral')
        axes[1].set_title('Tasa de Optimalidad por Severidad')
        axes[1].set_xlabel('Severity Level')
        axes[1].set_ylabel('Optimal Rate (%)')

        plt.tight_layout()
        plt.savefig('notebooks/02_severity_analysis.png', dpi=300, bbox_inches='tight')
        plt.close()
        logger.info("Gráfico saved: 02_severity_analysis.png")

    def plot_feature_correlations(self):
        """Matriz de correlación de features"""
        if self.df is None:
            return

        # Seleccionar columnas numéricas
        numeric_cols = self.df.select_dtypes(include=[np.number]).columns
        corr_matrix = self.df[numeric_cols].corr()

        # Hacer la figura más grande para mejor legibilidad
        fig, ax = plt.subplots(figsize=(14, 10))

        # Heatmap de correlación
        sns.heatmap(corr_matrix, annot=True, fmt='.2f', cmap='coolwarm', center=0,
                    square=True, ax=ax, cbar_kws={"shrink": 0.8})
        plt.title('Matriz de Correlación de Features')
        plt.tight_layout()
        plt.savefig('notebooks/03_correlation_matrix.png', dpi=300, bbox_inches='tight')
        plt.close()
        logger.info("Gráfico saved: 03_correlation_matrix.png")

    def plot_distance_impact(self):
        """Impacto de distancia en optimalidad"""
        if self.df is None:
            return

        fig, axes = plt.subplots(1, 2, figsize=(12, 4))

        # Distribución de distancia
        axes[0].hist(self.df['nearest_ambulance_distance_km'], bins=30, color='skyblue', edgecolor='black')
        axes[0].set_title('Distribución de Distancia a Ambulancia')
        axes[0].set_xlabel('Distancia (km)')
        axes[0].set_ylabel('Frecuencia')

        # Distancia vs Optimalidad
        self.df.boxplot(column='nearest_ambulance_distance_km', by='was_optimal', ax=axes[1])
        axes[1].set_title('Distancia por Estado de Optimalidad')
        axes[1].set_xlabel('Optimal')
        axes[1].set_ylabel('Distancia (km)')
        plt.suptitle('')

        plt.tight_layout()
        plt.savefig('notebooks/04_distance_impact.png', dpi=300, bbox_inches='tight')
        plt.close()
        logger.info("Gráfico saved: 04_distance_impact.png")

    def plot_response_time_impact(self):
        """Impacto de tiempo de respuesta en optimalidad"""
        if self.df is None:
            return

        fig, axes = plt.subplots(1, 2, figsize=(12, 4))

        # Distribución de tiempo de respuesta
        axes[0].hist(self.df['actual_response_time_minutes'], bins=30, color='lightgreen', edgecolor='black')
        axes[0].set_title('Distribución de Tiempo de Respuesta Real')
        axes[0].set_xlabel('Minutos')
        axes[0].set_ylabel('Frecuencia')

        # Tiempo vs Optimalidad
        self.df.boxplot(column='actual_response_time_minutes', by='was_optimal', ax=axes[1])
        axes[1].set_title('Tiempo de Respuesta por Estado de Optimalidad')
        axes[1].set_xlabel('Optimal')
        axes[1].set_ylabel('Minutos')
        plt.suptitle('')

        plt.tight_layout()
        plt.savefig('notebooks/05_response_time_impact.png', dpi=300, bbox_inches='tight')
        plt.close()
        logger.info("Gráfico saved: 05_response_time_impact.png")

    def plot_satisfaction_analysis(self):
        """Análisis de satisfacción vs optimalidad"""
        if self.df is None:
            return

        fig, axes = plt.subplots(1, 2, figsize=(12, 4))

        # Satisfacción de paramedics
        self.df.boxplot(column='paramedic_satisfaction_rating', by='was_optimal', ax=axes[0])
        axes[0].set_title('Satisfacción de Paramedics vs Optimalidad')
        axes[0].set_xlabel('Optimal')
        axes[0].set_ylabel('Rating')

        # Satisfacción de pacientes
        self.df.boxplot(column='patient_satisfaction_rating', by='was_optimal', ax=axes[1])
        axes[1].set_title('Satisfacción de Pacientes vs Optimalidad')
        axes[1].set_xlabel('Optimal')
        axes[1].set_ylabel('Rating')

        plt.suptitle('')
        plt.tight_layout()
        plt.savefig('notebooks/06_satisfaction_analysis.png', dpi=300, bbox_inches='tight')
        plt.close()
        logger.info("Gráfico saved: 06_satisfaction_analysis.png")

    def plot_availability_impact(self):
        """Impacto de disponibilidad de recursos"""
        if self.df is None:
            return

        fig, axes = plt.subplots(2, 2, figsize=(12, 8))

        # Ambulancias disponibles vs Optimalidad
        self.df.boxplot(column='available_ambulances_count', by='was_optimal', ax=axes[0, 0])
        axes[0, 0].set_title('Ambulancias Disponibles')
        axes[0, 0].set_xlabel('Optimal')

        # Paramedics disponibles vs Optimalidad
        self.df.boxplot(column='paramedics_available_count', by='was_optimal', ax=axes[0, 1])
        axes[0, 1].set_title('Paramedics Disponibles')
        axes[0, 1].set_xlabel('Optimal')

        # Nurses disponibles vs Optimalidad
        self.df.boxplot(column='nurses_available_count', by='was_optimal', ax=axes[1, 0])
        axes[1, 0].set_title('Nurses Disponibles')
        axes[1, 0].set_xlabel('Optimal')

        # Porcentaje de ambulancias ocupadas
        self.df.boxplot(column='ambulances_busy_percentage', by='was_optimal', ax=axes[1, 1])
        axes[1, 1].set_title('Porcentaje de Ambulancias Ocupadas')
        axes[1, 1].set_xlabel('Optimal')

        plt.suptitle('')
        plt.tight_layout()
        plt.savefig('notebooks/07_availability_impact.png', dpi=300, bbox_inches='tight')
        plt.close()
        logger.info("Gráfico saved: 07_availability_impact.png")

    def plot_time_patterns(self):
        """Patrones por hora y día"""
        if self.df is None:
            return

        fig, axes = plt.subplots(1, 2, figsize=(12, 4))

        # Optimalidad por hora del día
        hourly_optimal = self.df.groupby('hour_of_day')['was_optimal'].agg(['sum', 'count'])
        hourly_optimal['rate'] = hourly_optimal['sum'] / hourly_optimal['count'] * 100
        hourly_optimal['rate'].plot(ax=axes[0], color='purple', marker='o')
        axes[0].set_title('Tasa de Optimalidad por Hora del Día')
        axes[0].set_xlabel('Hora del Día')
        axes[0].set_ylabel('Optimal Rate (%)')
        axes[0].grid(True, alpha=0.3)

        # Optimalidad por día de la semana
        daily_optimal = self.df.groupby('day_of_week')['was_optimal'].agg(['sum', 'count'])
        daily_optimal['rate'] = daily_optimal['sum'] / daily_optimal['count'] * 100
        daily_names = ['Lunes', 'Martes', 'Miércoles', 'Jueves', 'Viernes', 'Sábado', 'Domingo']
        axes[1].bar(range(7), daily_optimal['rate'].values, color='teal', alpha=0.7)
        axes[1].set_title('Tasa de Optimalidad por Día de la Semana')
        axes[1].set_xlabel('Día')
        axes[1].set_ylabel('Optimal Rate (%)')
        axes[1].set_xticks(range(7))
        axes[1].set_xticklabels(daily_names, rotation=45)

        plt.tight_layout()
        plt.savefig('notebooks/08_time_patterns.png', dpi=300, bbox_inches='tight')
        plt.close()
        logger.info("Gráfico saved: 08_time_patterns.png")

    def run_analysis(self):
        """Ejecutar análisis completo"""
        if not self.load_data():
            return False

        print("\n" + "=" * 70)
        print("ANALISIS EXPLORATORIO DE DATOS (EDA)")
        print("=" * 70)

        # Estadísticas básicas
        self.print_basic_stats()

        # Generar visualizaciones
        print("\n" + "-" * 70)
        print("GENERANDO VISUALIZACIONES...")
        print("-" * 70)

        self.plot_target_distribution()
        self.plot_severity_distribution()
        self.plot_feature_correlations()
        self.plot_distance_impact()
        self.plot_response_time_impact()
        self.plot_satisfaction_analysis()
        self.plot_availability_impact()
        self.plot_time_patterns()

        print("\n" + "=" * 70)
        print("ANALISIS COMPLETADO")
        print("=" * 70)
        print(f"Visualizaciones guardadas en: notebooks/")
        print("Archivos generados:")
        print("  1. 01_target_distribution.png")
        print("  2. 02_severity_analysis.png")
        print("  3. 03_correlation_matrix.png")
        print("  4. 04_distance_impact.png")
        print("  5. 05_response_time_impact.png")
        print("  6. 06_satisfaction_analysis.png")
        print("  7. 07_availability_impact.png")
        print("  8. 08_time_patterns.png")

        return True


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    analyzer = ExploratoryAnalysis(
        server='192.168.1.38',
        database='ms_ml_despacho',
        username='sa',
        password='1234'
    )

    if analyzer.run_analysis():
        analyzer.disconnect()
    else:
        print("Error durante el análisis")
