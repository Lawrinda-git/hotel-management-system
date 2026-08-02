import React, { useState } from 'react';
import { View, Text, TextInput, TouchableOpacity, Alert, ScrollView } from 'react-native';

const SignUpScreen = ({ navigation }) => {
  const [fullName, setFullName] = useState('');
  const [email, setEmail] = useState('');
  const [phone, setPhone] = useState('');
  const [password, setPassword] = useState('');
  const [submitting, setSubmitting] = useState(false);

  const handleSignUp = async () => {
    if (!fullName.trim() || !email.trim() || !phone.trim() || !password) {
      Alert.alert('Missing details', 'Please fill in all fields.');
      return;
    }
    if (password.length < 6) {
      Alert.alert('Weak password', 'Password must be at least 6 characters.');
      return;
    }
    setSubmitting(true);
    try {
      const response = await fetch('http://localhost:8000/api/auth/register/', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          full_name: fullName,
          email,
          country_code: '+233',
          phone,
          password,
        }),
      });

      const data = await response.json();
      if (response.ok) {
        Alert.alert('Account created', 'Your account is ready. Please sign in.', [
          { text: 'OK', onPress: () => navigation.navigate('Login') },
        ]);
      } else {
        Alert.alert('Sign Up Failed', data.detail || 'Unable to create account');
      }
    } catch (error) {
      Alert.alert('Error', 'Unable to connect to server');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <ScrollView contentContainerStyle={{ flexGrow: 1, justifyContent: 'center', padding: 20, backgroundColor: '#f7f9fb' }}>
      <Text style={{ fontSize: 28, fontWeight: '700', color: '#00288e', textAlign: 'center' }}>
        Join StayHub
      </Text>
      <Text style={{ color: '#444653', textAlign: 'center', marginBottom: 32 }}>
        Create your account to start booking
      </Text>

      <TextInput
        placeholder="Full Name"
        value={fullName}
        onChangeText={setFullName}
        autoCapitalize="words"
        style={inputStyle}
      />
      <TextInput
        placeholder="Email"
        value={email}
        onChangeText={setEmail}
        autoCapitalize="none"
        keyboardType="email-address"
        style={inputStyle}
      />
      <TextInput
        placeholder="Phone (e.g. 24 123 4567)"
        value={phone}
        onChangeText={setPhone}
        keyboardType="phone-pad"
        style={inputStyle}
      />
      <TextInput
        placeholder="Password"
        value={password}
        onChangeText={setPassword}
        secureTextEntry
        style={{ ...inputStyle, marginBottom: 24 }}
      />

      <TouchableOpacity
        onPress={handleSignUp}
        disabled={submitting}
        style={{ backgroundColor: submitting ? '#8f9cd6' : '#00288e', borderRadius: 12, padding: 16, alignItems: 'center' }}
      >
        <Text style={{ color: '#ffffff', fontWeight: '600' }}>
          {submitting ? 'Creating account...' : 'Create Account'}
        </Text>
      </TouchableOpacity>

      <TouchableOpacity onPress={() => navigation.navigate('Login')} style={{ marginTop: 16, alignItems: 'center' }}>
        <Text style={{ color: '#00288e' }}>Already have an account? Sign In</Text>
      </TouchableOpacity>
    </ScrollView>
  );
};

const inputStyle = {
  backgroundColor: '#ffffff',
  borderRadius: 12,
  padding: 16,
  marginBottom: 16,
};

export default SignUpScreen;
