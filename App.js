import React, { useState, useEffect, useRef } from 'react';
import { 
  StyleSheet, Text, View, TextInput, TouchableOpacity, 
  FlatList, SafeAreaView, StatusBar, Alert 
} from 'react-native';

const PIN_CODE = "20092010";

// Укажи ключ в зависимости от того, чьё это устройство:
// - На твой ПК/телефон: "key_amir_pc_9981" или "key_amir_phone_4412"
// - На её телефон: "key_faye_phone_7730"
const DEVICE_KEY = "key_amir_phone_4412"; 

// Укажи адрес твоего сервера на Render (после развертывания)
const SERVER_URL = `wss://secret-calculator-chat.onrender.com/ws?device_key=${DEVICE_KEY}`;

export default function App() {
  const [calcInput, setCalcInput] = useState('');
  const [isUnlocked, setIsUnlocked] = useState(false);
  const [messages, setMessages] = useState([]);
  const [text, setText] = useState('');
  const [isConnected, setIsConnected] = useState(false);
  
  const ws = useRef(null);

  const isAmir = DEVICE_KEY.includes('amir');
  const headerTitle = isAmir ? "Amir and lovely" : "Faye and boyfriend";
  const contactName = isAmir ? "Любимая" : "Любимый";

  useEffect(() => {
    if (isUnlocked) {
      connectWebSocket();
    }
    return () => {
      if (ws.current) ws.current.close();
    };
  }, [isUnlocked]);

  const connectWebSocket = () => {
    ws.current = new WebSocket(SERVER_URL);

    ws.current.onopen = () => {
      setIsConnected(true);
    };

    ws.current.onmessage = (e) => {
      const data = JSON.parse(e.data);
      setMessages(prev => [...prev, data]);
    };

    ws.current.onerror = () => {
      setIsConnected(false);
    };

    ws.current.onclose = (e) => {
      setIsConnected(false);
      if (e.code === 1008) {
        Alert.alert("Ошибка доступа", "Данное устройство не авторизовано!");
        return;
      }
      setTimeout(() => {
        if (isUnlocked) connectWebSocket();
      }, 3000);
    };
  };

  const handleCalcPress = (val) => {
    if (val === '=') {
      if (calcInput === PIN_CODE) {
        setIsUnlocked(true);
      } else {
        try {
          setCalcInput(eval(calcInput).toString());
        } catch {
          setCalcInput('Ошибка');
        }
      }
    } else if (val === 'C') {
      setCalcInput('');
    } else {
      setCalcInput(prev => prev + val);
    }
  };

  const sendMessage = () => {
    if (text.trim() === '') return;
    
    const messageData = {
      text: text,
      time: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
    };

    if (ws.current && ws.current.readyState === WebSocket.OPEN) {
      ws.current.send(JSON.stringify(messageData));
      setText('');
    } else {
      Alert.alert("Нет связи", "Сервер недоступен");
    }
  };

  if (!isUnlocked) {
    return (
      <SafeAreaView style={styles.calcContainer}>
        <StatusBar barStyle="light-content" />
        <Text style={styles.calcDisplay}>{calcInput || '0'}</Text>
        <View style={styles.calcGrid}>
          {['7','8','9','/','4','5','6','*','1','2','3','-','C','0','=','+'].map((item) => (
            <TouchableOpacity key={item} style={styles.calcBtn} onPress={() => handleCalcPress(item)}>
              <Text style={styles.calcBtnText}>{item}</Text>
            </TouchableOpacity>
          ))}
        </View>
      </SafeAreaView>
    );
  }

  return (
    <SafeAreaView style={styles.chatContainer}>
      <StatusBar barStyle="light-content" />
      <View style={styles.header}>
        <Text style={styles.headerSubtitle}>{headerTitle}</Text>
        <Text style={styles.headerTitle}>{contactName}</Text>
        <View style={styles.statusRow}>
          <View style={[styles.statusDot, { backgroundColor: isConnected ? '#30d158' : '#ff453a' }]} />
          <Text style={styles.statusText}>{isConnected ? "защищенный канал" : "подключение..."}</Text>
        </View>
      </View>

      <FlatList
        data={messages}
        keyExtractor={(_, index) => index.toString()}
        renderItem={({ item }) => {
          const isMyMsg = item.sender === (isAmir ? 'amir' : 'faye');
          return (
            <View style={[styles.msgBubble, isMyMsg ? styles.myMsg : styles.theirMsg]}>
              <Text style={styles.msgText}>{item.text}</Text>
              <Text style={styles.msgTime}>{item.time}</Text>
            </View>
          );
        }}
      />

      <View style={styles.inputBar}>
        <TextInput 
          style={styles.input} 
          placeholder="Сообщение..." 
          placeholderTextColor="#8e8e93"
          value={text} 
          onChangeText={setText} 
        />
        <TouchableOpacity style={styles.sendBtn} onPress={sendMessage}>
          <Text style={{color: '#fff', fontWeight: 'bold', fontSize: 16}}>➤</Text>
        </TouchableOpacity>
      </View>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  calcContainer: { flex: 1, backgroundColor: '#000', justifyContent: 'flex-end', padding: 20 },
  calcDisplay: { color: '#fff', fontSize: 48, textAlign: 'right', marginBottom: 20 },
  calcGrid: { flexDirection: 'row', flexWrap: 'wrap', justifyContent: 'space-between' },
  calcBtn: { width: '22%', height: 70, backgroundColor: '#1c1c1e', justifyContent: 'center', alignItems: 'center', marginBottom: 15, borderRadius: 35 },
  calcBtnText: { color: '#fff', fontSize: 28 },
  chatContainer: { flex: 1, backgroundColor: '#000' },
  header: { paddingVertical: 12, backgroundColor: '#1c1c1e', alignItems: 'center', borderBottomWidth: 0.5, borderBottomColor: '#38383a' },
  headerSubtitle: { color: '#8e8e93', fontSize: 11 },
  headerTitle: { color: '#fff', fontSize: 17, fontWeight: '600', marginTop: 2 },
  statusRow: { flexDirection: 'row', alignItems: 'center', marginTop: 4 },
  statusDot: { width: 6, height: 6, borderRadius: 3, marginRight: 5 },
  statusText: { color: '#8e8e93', fontSize: 10 },
  inputBar: { flexDirection: 'row', padding: 10, backgroundColor: '#1c1c1e', alignItems: 'center' },
  input: { flex: 1, backgroundColor: '#2c2c2e', color: '#fff', borderRadius: 20, paddingHorizontal: 15, height: 40, fontSize: 15 },
  sendBtn: { marginLeft: 10, backgroundColor: '#0a84ff', width: 36, height: 36, borderRadius: 18, justifyContent: 'center', alignItems: 'center' },
  msgBubble: { padding: 10, borderRadius: 16, marginVertical: 4, maxWidth: '75%', marginHorizontal: 12 },
  myMsg: { backgroundColor: '#0a84ff', alignSelf: 'flex-end' },
  theirMsg: { backgroundColor: '#2c2c2e', alignSelf: 'flex-start' },
  msgText: { color: '#fff', fontSize: 15 },
  msgTime: { color: 'rgba(255,255,255,0.5)', fontSize: 9, alignSelf: 'flex-end', marginTop: 4 }
});