import React, { useState, useEffect } from 'react';
import './App.css';

function App() {
  const [botStatus, setBotStatus] = useState('checking');
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(true);

  const backendUrl = process.env.REACT_APP_BACKEND_URL || 'http://localhost:8001';

  useEffect(() => {
    checkBotStatus();
    // Update status every 30 seconds
    const interval = setInterval(checkBotStatus, 30000);
    return () => clearInterval(interval);
  }, []);

  const checkBotStatus = async () => {
    try {
      const response = await fetch(`${backendUrl}/api/health`);
      if (response.ok) {
        setBotStatus('online');
      } else {
        setBotStatus('offline');
      }
    } catch (error) {
      setBotStatus('offline');
    } finally {
      setLoading(false);
    }
  };

  const setWebhook = async () => {
    try {
      setLoading(true);
      const response = await fetch(`${backendUrl}/api/set_webhook`, {
        method: 'POST'
      });
      if (response.ok) {
        const data = await response.json();
        alert(`Webhook установлен: ${data.url}`);
      } else {
        alert('Ошибка установки webhook');
      }
    } catch (error) {
      alert('Ошибка соединения с сервером');
    } finally {
      setLoading(false);
    }
  };

  const getStatusColor = () => {
    switch (botStatus) {
      case 'online': return 'text-green-500';
      case 'offline': return 'text-red-500';
      default: return 'text-yellow-500';
    }
  };

  const getStatusText = () => {
    switch (botStatus) {
      case 'online': return 'Онлайн';
      case 'offline': return 'Офлайн';
      default: return 'Проверка...';
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-blue-50 to-indigo-100 flex items-center justify-center">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto mb-4"></div>
          <p className="text-gray-600">Загрузка...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-50 to-indigo-100">
      <div className="container mx-auto px-4 py-8">
        {/* Header */}
        <div className="text-center mb-12">
          <h1 className="text-4xl font-bold text-gray-800 mb-4">
            🤖 Семейный Бот-Помощник
          </h1>
          <p className="text-lg text-gray-600 max-w-2xl mx-auto">
            Умный помощник для всей семьи с анализом питания, фитнес советами и многим другим
          </p>
        </div>

        {/* Bot Status */}
        <div className="max-w-4xl mx-auto mb-8">
          <div className="bg-white rounded-lg shadow-lg p-6">
            <div className="flex items-center justify-between mb-6">
              <div className="flex items-center">
                <div className={`w-4 h-4 rounded-full mr-3 ${botStatus === 'online' ? 'bg-green-500' : 'bg-red-500'}`}></div>
                <h2 className="text-xl font-semibold text-gray-800">Статус бота</h2>
              </div>
              <span className={`font-medium ${getStatusColor()}`}>
                {getStatusText()}
              </span>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              <div className="bg-gray-50 rounded-lg p-4">
                <h3 className="font-semibold text-gray-800 mb-2">Telegram Bot</h3>
                <p className="text-sm text-gray-600 mb-2">@DMPlove_bot</p>
                <a 
                  href="https://t.me/DMPlove_bot" 
                  target="_blank" 
                  rel="noopener noreferrer"
                  className="inline-block bg-blue-500 text-white px-4 py-2 rounded-lg hover:bg-blue-600 transition-colors"
                >
                  Открыть в Telegram
                </a>
              </div>
              
              <div className="bg-gray-50 rounded-lg p-4">
                <h3 className="font-semibold text-gray-800 mb-2">Настройка</h3>
                <p className="text-sm text-gray-600 mb-2">Установить webhook</p>
                <button 
                  onClick={setWebhook}
                  className="bg-green-500 text-white px-4 py-2 rounded-lg hover:bg-green-600 transition-colors"
                >
                  Настроить бота
                </button>
              </div>
            </div>
          </div>
        </div>

        {/* Features */}
        <div className="max-w-6xl mx-auto mb-8">
          <h2 className="text-2xl font-bold text-gray-800 mb-6 text-center">Функции бота</h2>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            <div className="bg-white rounded-lg shadow-lg p-6">
              <div className="text-3xl mb-4">📸</div>
              <h3 className="text-lg font-semibold text-gray-800 mb-2">Анализ еды</h3>
              <p className="text-gray-600 text-sm">
                Автоматический анализ фотографий еды с подсчетом калорий, БЖУ и ведением статистики
              </p>
            </div>

            <div className="bg-white rounded-lg shadow-lg p-6">
              <div className="text-3xl mb-4">💪</div>
              <h3 className="text-lg font-semibold text-gray-800 mb-2">Фитнес советы</h3>
              <p className="text-gray-600 text-sm">
                Персональные рекомендации по фитнесу и питанию на основе вашего профиля
              </p>
            </div>

            <div className="bg-white rounded-lg shadow-lg p-6">
              <div className="text-3xl mb-4">👤</div>
              <h3 className="text-lg font-semibold text-gray-800 mb-2">Профиль здоровья</h3>
              <p className="text-gray-600 text-sm">
                Ведение персональных данных о здоровье и отслеживание динамики
              </p>
            </div>

            <div className="bg-white rounded-lg shadow-lg p-6">
              <div className="text-3xl mb-4">🤖</div>
              <h3 className="text-lg font-semibold text-gray-800 mb-2">ИИ помощник</h3>
              <p className="text-gray-600 text-sm">
                Свободное общение с ChatGPT с выбором модели и настройкой промптов
              </p>
            </div>

            <div className="bg-white rounded-lg shadow-lg p-6">
              <div className="text-3xl mb-4">🎬</div>
              <h3 className="text-lg font-semibold text-gray-800 mb-2">Фильмы и сериалы</h3>
              <p className="text-gray-600 text-sm">
                Рекомендации фильмов и сериалов на основе ваших предпочтений
              </p>
            </div>

            <div className="bg-white rounded-lg shadow-lg p-6">
              <div className="text-3xl mb-4">📊</div>
              <h3 className="text-lg font-semibold text-gray-800 mb-2">Статистика</h3>
              <p className="text-gray-600 text-sm">
                Детальная статистика по питанию за день, неделю и месяц
              </p>
            </div>
          </div>
        </div>

        {/* Instructions */}
        <div className="max-w-4xl mx-auto">
          <div className="bg-white rounded-lg shadow-lg p-6">
            <h2 className="text-xl font-semibold text-gray-800 mb-4">Как использовать бота</h2>
            <div className="space-y-4">
              <div className="flex items-start">
                <span className="bg-blue-100 text-blue-800 text-xs font-medium px-2.5 py-1 rounded-full mr-3 mt-0.5">1</span>
                <div>
                  <h3 className="font-medium text-gray-800">Начните диалог</h3>
                  <p className="text-sm text-gray-600">Нажмите /start в чате с ботом</p>
                </div>
              </div>
              
              <div className="flex items-start">
                <span className="bg-blue-100 text-blue-800 text-xs font-medium px-2.5 py-1 rounded-full mr-3 mt-0.5">2</span>
                <div>
                  <h3 className="font-medium text-gray-800">Отправьте фото еды</h3>
                  <p className="text-sm text-gray-600">Бот автоматически проанализирует блюдо и подсчитает калории</p>
                </div>
              </div>
              
              <div className="flex items-start">
                <span className="bg-blue-100 text-blue-800 text-xs font-medium px-2.5 py-1 rounded-full mr-3 mt-0.5">3</span>
                <div>
                  <h3 className="font-medium text-gray-800">Настройте профиль</h3>
                  <p className="text-sm text-gray-600">Укажите свои данные для персональных рекомендаций</p>
                </div>
              </div>
              
              <div className="flex items-start">
                <span className="bg-blue-100 text-blue-800 text-xs font-medium px-2.5 py-1 rounded-full mr-3 mt-0.5">4</span>
                <div>
                  <h3 className="font-medium text-gray-800">Используйте все функции</h3>
                  <p className="text-sm text-gray-600">Получайте советы, общайтесь с ИИ, смотрите статистику</p>
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* Footer */}
        <div className="text-center mt-12 text-gray-600">
          <p>© 2024 Семейный Бот-Помощник. Работает на базе OpenAI и Telegram API</p>
        </div>
      </div>
    </div>
  );
}

export default App;