import React, { useState } from 'react';
import { View, Text, TextInput, TouchableOpacity, Alert } from 'react-native';
import { API_BASE_URL, HEADERS } from '../config/api';

const LoginScreen = ({ navigation }) => {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');

  const handleLogin = async () => {
    try {
      const response = await fetch(`${API_BASE_URL}/api/auth/login/`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email, password }),
      });
      
      const data = await response.json();
      if (response.ok) {
        navigation.navigate('MainApp');
      } else {
        Alert.alert('Login Failed', data.detail || 'Invalid credentials');
      }
    } catch (error) {
      Alert.alert('Error', 'Unable to connect to server');
    }
  };

  return (
    <View style={{ flex: 1, justifyContent: 'center', padding: 20, backgroundColor: '#f7f9fb' }}>
      <Text style={{ fontSize: 28, fontWeight: '700', color: '#00288e', textAlign: 'center' }}>
        StayHub
      </Text>
      <Text style={{ color: '#444653', textAlign: 'center', marginBottom: 32 }}>
        Sign in to your account
      </Text>
      
      <TextInput
        placeholder="Email"
        value={email}
        onChangeText={setEmail}
        autoCapitalize="none"
        keyboardType="email-address"
        style={{ backgroundColor: '#ffffff', borderRadius: 12, padding: 16, marginBottom: 16 }}
      />
      <TextInput
        placeholder="Password"
        value={password}
        onChangeText={setPassword}
        secureTextEntry
        style={{ backgroundColor: '#ffffff', borderRadius: 12, padding: 16, marginBottom: 24 }}
      />
      
      <TouchableOpacity 
        onPress={handleLogin}
        style={{ backgroundColor: '#00288e', borderRadius: 12, padding: 16, alignItems: 'center' }}
      >
        <Text style={{ color: '#ffffff', fontWeight: '600' }}>Sign In</Text>
      </TouchableOpacity>
      
      <TouchableOpacity onPress={() => navigation.navigate('SignUp')} style={{ marginTop: 16, alignItems: 'center' }}>
        <Text style={{ color: '#00288e' }}>Don't have an account? Sign Up</Text>
      </TouchableOpacity>
    </View>
  );
};

export default LoginScreen;